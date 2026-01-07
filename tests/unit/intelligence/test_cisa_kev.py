"""Unit tests for CISA KEV Source Integration.

Tests cover:
- KevEntry dataclass and JSON parsing
- KevCatalog caching behavior
- CisaKevSource interface implementation
- Query matching and result conversion
"""

import json
import pytest
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.intelligence import IntelPriority, IntelResult, IntelligenceSource


# =============================================================================
# Phase 1: KEV Data Models Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestKevEntry:
    """Tests for KevEntry dataclass (Task 1.1)."""

    def test_kev_entry_accepts_all_required_fields(self) -> None:
        """KevEntry dataclass accepts all required fields from CISA JSON."""
        # Importing here to allow test to fail if module doesn't exist yet
        from cyberred.intelligence.sources.cisa_kev import KevEntry

        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Apache Log4j Remote Code Execution Vulnerability",
            date_added="2021-12-10",
            short_description="Apache Log4j2 JNDI features...",
            required_action="Apply updates per vendor instructions.",
            due_date="2021-12-24",
            notes="",
        )

        assert entry.cve_id == "CVE-2021-44228"
        assert entry.vendor_project == "Apache"
        assert entry.product == "Log4j"
        assert entry.vulnerability_name == "Apache Log4j Remote Code Execution Vulnerability"
        assert entry.date_added == "2021-12-10"
        assert entry.short_description == "Apache Log4j2 JNDI features..."
        assert entry.required_action == "Apply updates per vendor instructions."
        assert entry.due_date == "2021-12-24"
        assert entry.notes == ""

    def test_kev_entry_from_json_parses_raw_entry(self) -> None:
        """KevEntry.from_json() correctly parses raw KEV JSON entries."""
        from cyberred.intelligence.sources.cisa_kev import KevEntry

        raw_json = {
            "cveID": "CVE-2021-44228",
            "vendorProject": "Apache",
            "product": "Log4j",
            "vulnerabilityName": "Apache Log4j Remote Code Execution Vulnerability",
            "dateAdded": "2021-12-10",
            "shortDescription": "Apache Log4j2 JNDI features...",
            "requiredAction": "Apply updates per vendor instructions.",
            "dueDate": "2021-12-24",
            "notes": "",
        }

        entry = KevEntry.from_json(raw_json)

        assert entry.cve_id == "CVE-2021-44228"
        assert entry.vendor_project == "Apache"
        assert entry.product == "Log4j"
        assert entry.vulnerability_name == "Apache Log4j Remote Code Execution Vulnerability"
        assert entry.date_added == "2021-12-10"
        assert entry.short_description == "Apache Log4j2 JNDI features..."
        assert entry.required_action == "Apply updates per vendor instructions."
        assert entry.due_date == "2021-12-24"
        assert entry.notes == ""


# =============================================================================
# Phase 2: KEV Catalog Cache Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestKevCatalog:
    """Tests for KevCatalog caching behavior (Tasks 2.1, 2.2)."""

    def test_catalog_has_correct_feed_url(self) -> None:
        """KevCatalog.FEED_URL points to official CISA feed."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog

        expected_url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        assert KevCatalog.FEED_URL == expected_url

    def test_cache_file_uses_configured_base_path(self) -> None:
        """CACHE_FILE property returns path under configured storage base."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog

        catalog = KevCatalog()
        cache_file = catalog.CACHE_FILE

        assert cache_file.name == "kev_catalog.json"
        assert isinstance(cache_file, Path)

    def test_cache_ttl_is_24_hours(self) -> None:
        """CACHE_TTL is set to 24 hours per story requirements."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog

        assert KevCatalog.CACHE_TTL == timedelta(hours=24)

    def test_is_cache_valid_returns_false_for_stale_cache(self, tmp_path) -> None:
        """is_cache_valid() returns False for cache older than 24 hours."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock
        import time
        import os

        catalog = KevCatalog()

        # Create a real temp file and set its mtime to 25 hours ago
        cache_file = tmp_path / "kev_catalog.json"
        cache_file.write_text('{"vulnerabilities": []}')
        old_time = time.time() - (25 * 3600)
        os.utime(cache_file, (old_time, old_time))

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            assert catalog.is_cache_valid() is False

    def test_is_cache_valid_returns_true_for_recent_cache(self, tmp_path) -> None:
        """is_cache_valid() returns True for cache less than 24 hours old."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock

        catalog = KevCatalog()

        # Create a real temp file (its mtime will be current = recent)
        cache_file = tmp_path / "kev_catalog.json"
        cache_file.write_text('{"vulnerabilities": []}')

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            assert catalog.is_cache_valid() is True

    def test_is_cache_valid_returns_false_when_no_cache_exists(self, tmp_path) -> None:
        """is_cache_valid() returns False when cache file doesn't exist."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock

        catalog = KevCatalog()

        # Point to a non-existent file
        cache_file = tmp_path / "nonexistent.json"

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            assert catalog.is_cache_valid() is False

    def test_load_cached_returns_entries_when_valid(self, tmp_path) -> None:
        """load_cached() loads entries from valid cache file."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog, KevEntry
        from unittest.mock import patch, PropertyMock

        catalog = KevCatalog()
        cache_data = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2021-44228",
                    "vendorProject": "Apache",
                    "product": "Log4j",
                    "vulnerabilityName": "Log4j RCE",
                    "dateAdded": "2021-12-10",
                    "shortDescription": "desc",
                    "requiredAction": "patch",
                    "dueDate": "2021-12-24",
                    "notes": "",
                }
            ]
        }

        # Create cache file with valid data
        cache_file = tmp_path / "kev_catalog.json"
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            entries = catalog.load_cached()

            assert entries is not None
            assert len(entries) == 1
            assert entries[0].cve_id == "CVE-2021-44228"

    def test_load_cached_returns_none_when_invalid(self) -> None:
        """load_cached() returns None when cache is invalid."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch

        catalog = KevCatalog()

        with patch.object(catalog, "is_cache_valid", return_value=False):
            entries = catalog.load_cached()

            assert entries is None

    @pytest.mark.asyncio
    async def test_ensure_cached_uses_cache_if_valid(self) -> None:
        """ensure_cached() uses cached entries when cache is valid."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog, KevEntry
        from unittest.mock import patch, AsyncMock

        catalog = KevCatalog()
        cached_entries = [
            KevEntry(
                cve_id="CVE-2021-44228",
                vendor_project="Apache",
                product="Log4j",
                vulnerability_name="Log4j RCE",
                date_added="2021-12-10",
                short_description="desc",
                required_action="patch",
                due_date="2021-12-24",
                notes="",
            )
        ]

        with patch.object(catalog, "load_cached", return_value=cached_entries):
            with patch.object(catalog, "fetch", new_callable=AsyncMock) as mock_fetch:
                entries = await catalog.ensure_cached()

                assert entries == cached_entries
                mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_cached_fetches_if_no_cache(self) -> None:
        """ensure_cached() fetches from network if no valid cache exists."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog, KevEntry
        from unittest.mock import patch, AsyncMock

        catalog = KevCatalog()
        fetched_entries = [
            KevEntry(
                cve_id="CVE-2021-44228",
                vendor_project="Apache",
                product="Log4j",
                vulnerability_name="Log4j RCE",
                date_added="2021-12-10",
                short_description="desc",
                required_action="patch",
                due_date="2021-12-24",
                notes="",
            )
        ]

        with patch.object(catalog, "load_cached", return_value=None):
            with patch.object(
                catalog, "fetch", new_callable=AsyncMock, return_value=fetched_entries
            ) as mock_fetch:
                entries = await catalog.ensure_cached()

                assert entries == fetched_entries
                mock_fetch.assert_called_once()


# =============================================================================
# Phase 3: CisaKevSource Implementation Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestCisaKevSource:
    """Tests for CisaKevSource implementation (Tasks 3.1-3.4)."""

    def test_extends_intelligence_source(self) -> None:
        """CisaKevSource extends IntelligenceSource."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        assert isinstance(source, IntelligenceSource)

    def test_name_returns_cisa_kev(self) -> None:
        """CisaKevSource.name returns 'cisa_kev'."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        assert source.name == "cisa_kev"

    def test_priority_returns_cisa_kev_priority(self) -> None:
        """CisaKevSource.priority returns IntelPriority.CISA_KEV."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        assert source.priority == IntelPriority.CISA_KEV

    def test_timeout_is_5_seconds(self) -> None:
        """CisaKevSource.timeout is 5.0 seconds per FR74."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        assert source.timeout == 5.0

    @pytest.mark.asyncio
    async def test_query_returns_matching_cves(self) -> None:
        """query('Apache', '2.4.49') returns matching CVEs."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog, KevEntry
        from unittest.mock import patch, AsyncMock

        # Create mock catalog with Apache entry
        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.ensure_cached = AsyncMock(
            return_value=[
                KevEntry(
                    cve_id="CVE-2021-41773",
                    vendor_project="Apache",
                    product="HTTP Server",
                    vulnerability_name="Apache HTTP Server Path Traversal",
                    date_added="2021-11-03",
                    short_description="Path traversal in Apache 2.4.49",
                    required_action="Update to 2.4.51",
                    due_date="2021-11-17",
                    notes="",
                ),
                KevEntry(
                    cve_id="CVE-2021-44228",
                    vendor_project="Apache",
                    product="Log4j",
                    vulnerability_name="Log4j RCE",
                    date_added="2021-12-10",
                    short_description="Log4j JNDI",
                    required_action="Update",
                    due_date="2021-12-24",
                    notes="",
                ),
            ]
        )

        source = CisaKevSource(catalog=mock_catalog)
        results = await source.query("Apache", "2.4.49")

        # Should match Apache HTTP Server entry
        assert len(results) >= 1
        assert any(r.cve_id == "CVE-2021-41773" for r in results)

    @pytest.mark.asyncio
    async def test_query_returns_empty_for_no_matches(self) -> None:
        """query() returns empty list when no matches found."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog, KevEntry
        from unittest.mock import MagicMock, AsyncMock

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.ensure_cached = AsyncMock(
            return_value=[
                KevEntry(
                    cve_id="CVE-2021-44228",
                    vendor_project="Apache",
                    product="Log4j",
                    vulnerability_name="Log4j RCE",
                    date_added="2021-12-10",
                    short_description="Log4j JNDI",
                    required_action="Update",
                    due_date="2021-12-24",
                    notes="",
                )
            ]
        )

        source = CisaKevSource(catalog=mock_catalog)
        results = await source.query("NonExistent", "1.0.0")

        assert results == []

    @pytest.mark.asyncio
    async def test_query_is_case_insensitive(self) -> None:
        """query() performs case-insensitive vendor/product matching."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog, KevEntry
        from unittest.mock import MagicMock, AsyncMock

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.ensure_cached = AsyncMock(
            return_value=[
                KevEntry(
                    cve_id="CVE-2021-44228",
                    vendor_project="Apache",
                    product="Log4j",
                    vulnerability_name="Log4j RCE",
                    date_added="2021-12-10",
                    short_description="Log4j JNDI",
                    required_action="Update",
                    due_date="2021-12-24",
                    notes="",
                )
            ]
        )

        source = CisaKevSource(catalog=mock_catalog)
        
        # Test lowercase query matching uppercase entry
        results = await source.query("apache", "2.14.0")

        assert len(results) >= 1
        assert results[0].cve_id == "CVE-2021-44228"

    def test_intel_result_source_is_cisa_kev(self) -> None:
        """IntelResult.source from CisaKevSource is 'cisa_kev'."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="Log4j JNDI",
            required_action="Update",
            due_date="2021-12-24",
            notes="",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.source == "cisa_kev"

    def test_intel_result_priority_is_cisa_kev(self) -> None:
        """IntelResult.priority is IntelPriority.CISA_KEV (1)."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="Log4j JNDI",
            required_action="Update",
            due_date="2021-12-24",
            notes="",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.priority == IntelPriority.CISA_KEV
        assert result.priority == 1

    def test_intel_result_metadata_contains_kev_fields(self) -> None:
        """IntelResult.metadata contains KEV-specific fields."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="Log4j JNDI features cause RCE",
            required_action="Update to 2.17.0",
            due_date="2021-12-24",
            notes="test notes",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.metadata["vulnerability_name"] == "Log4j RCE"
        assert result.metadata["vendor_project"] == "Apache"
        assert result.metadata["product"] == "Log4j"
        assert result.metadata["date_added"] == "2021-12-10"
        assert result.metadata["due_date"] == "2021-12-24"
        assert result.metadata["required_action"] == "Update to 2.17.0"
        assert result.metadata["short_description"] == "Log4j JNDI features cause RCE"

    def test_intel_result_severity_is_critical(self) -> None:
        """All KEV results have severity='critical'."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="Log4j JNDI",
            required_action="Update",
            due_date="2021-12-24",
            notes="",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.severity == "critical"

    def test_intel_result_exploit_available_is_true(self) -> None:
        """All KEV results have exploit_available=True."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="Log4j JNDI",
            required_action="Update",
            due_date="2021-12-24",
            notes="",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.exploit_available is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_with_valid_cache(self) -> None:
        """health_check() returns True when cache is valid."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog
        from unittest.mock import MagicMock

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.is_cache_valid.return_value = True

        source = CisaKevSource(catalog=mock_catalog)
        result = await source.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_unreachable(self) -> None:
        """health_check() returns False when no cache and CISA unreachable."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog
        from unittest.mock import MagicMock, patch
        import aiohttp

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.is_cache_valid.return_value = False

        source = CisaKevSource(catalog=mock_catalog)

        # Mock aiohttp to simulate network failure using patch on the module
        with patch("cyberred.intelligence.sources.cisa_kev.aiohttp.ClientSession") as mock_session_class:
            # Create a mock that raises ClientError when used as async context manager
            async def raise_client_error(*args, **kwargs):
                raise aiohttp.ClientError()

            mock_session = MagicMock()
            mock_session.__aenter__ = raise_client_error
            mock_session_class.return_value = mock_session

            result = await source.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_cisa_reachable(self) -> None:
        """health_check() returns True when no cache but CISA is reachable."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.is_cache_valid.return_value = False

        source = CisaKevSource(catalog=mock_catalog)

        # Mock aiohttp to simulate successful network check
        with patch("cyberred.intelligence.sources.cisa_kev.aiohttp.ClientSession") as mock_session_class:
            # Create a mock that returns 200 status
            mock_response = MagicMock()
            mock_response.status = 200

            async def mock_aenter(*args, **kwargs):
                return mock_session

            async def mock_head_aenter(*args, **kwargs):
                return mock_response

            mock_head = MagicMock()
            mock_head.__aenter__ = mock_head_aenter
            mock_head.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.__aenter__ = mock_aenter
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head.return_value = mock_head
            mock_session_class.return_value = mock_session

            result = await source.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_query_returns_empty_on_exception(self) -> None:
        """query() returns empty list on exception (per ERR3)."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevCatalog
        from unittest.mock import MagicMock, AsyncMock

        mock_catalog = MagicMock(spec=KevCatalog)
        mock_catalog.ensure_cached = AsyncMock(side_effect=Exception("Network error"))

        source = CisaKevSource(catalog=mock_catalog)
        results = await source.query("Apache", "2.4.49")

        assert results == []


# =============================================================================
# Edge Case Tests for Coverage
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for additional coverage."""

    def test_load_cached_returns_none_on_json_error(self, tmp_path) -> None:
        """load_cached() returns None when cache contains invalid JSON."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock

        catalog = KevCatalog()
        cache_file = tmp_path / "kev_catalog.json"
        cache_file.write_text("not valid json {{{{")

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            entries = catalog.load_cached()
            assert entries is None

    @pytest.mark.asyncio
    async def test_matches_both_vendor_and_product(self) -> None:
        """_matches_service returns 0.9 confidence when both vendor and product match."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        # Entry where "log" appears in both vendor ("ApacheLog") and product ("Log4j")
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="ApacheLog",  # Contains "log"
            product="Log4j",  # Contains "log"
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="desc",
            required_action="patch",
            due_date="2021-12-24",
            notes="",
        )

        matches, confidence = source._matches_service(entry, "log", "1.0")
        assert matches is True
        assert confidence == 0.9  # Both match = 0.9

    @pytest.mark.asyncio
    async def test_matches_exact_vendor(self) -> None:
        """_matches_service returns 1.0 confidence for exact vendor match."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache",
            product="Log4j",
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="desc",
            required_action="patch",
            due_date="2021-12-24",
            notes="",
        )

        matches, confidence = source._matches_service(entry, "Apache", "1.0")
        assert matches is True
        assert confidence == 1.0  # Exact match = 1.0


# =============================================================================
# Fetch Method Coverage Tests
# =============================================================================


@pytest.mark.unit
class TestKevCatalogFetch:
    """Tests for KevCatalog.fetch() to achieve 100% coverage (lines 177-198)."""

    @pytest.mark.asyncio
    async def test_fetch_downloads_and_caches_catalog(self, tmp_path) -> None:
        """fetch() downloads KEV catalog from CISA and caches locally."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock, AsyncMock, MagicMock

        catalog = KevCatalog()
        cache_file = tmp_path / "kev_catalog.json"

        # Mock response data
        mock_data = {
            "catalogVersion": "2025.01.07",
            "vulnerabilities": [
                {
                    "cveID": "CVE-2021-44228",
                    "vendorProject": "Apache",
                    "product": "Log4j",
                    "vulnerabilityName": "Log4j RCE",
                    "dateAdded": "2021-12-10",
                    "shortDescription": "desc",
                    "requiredAction": "patch",
                    "dueDate": "2021-12-24",
                    "notes": "",
                }
            ],
        }

        # Create mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=mock_data)

        # Create mock session
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            with patch("cyberred.intelligence.sources.cisa_kev.aiohttp.ClientSession") as mock_session_class:
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

                entries = await catalog.fetch()

                # Verify entries were parsed
                assert len(entries) == 1
                assert entries[0].cve_id == "CVE-2021-44228"

                # Verify cache file was created
                assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_fetch_creates_cache_directory(self, tmp_path) -> None:
        """fetch() creates cache directory if it doesn't exist."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock, AsyncMock, MagicMock

        catalog = KevCatalog()
        # Use a nested path that doesn't exist
        cache_file = tmp_path / "nested" / "dir" / "kev_catalog.json"

        mock_data = {
            "catalogVersion": "2025.01.07",
            "vulnerabilities": [],
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=mock_data)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            with patch("cyberred.intelligence.sources.cisa_kev.aiohttp.ClientSession") as mock_session_class:
                mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)

                await catalog.fetch()

                # Verify nested directory was created
                assert cache_file.parent.exists()


@pytest.mark.unit
class TestMatchesServiceBranches:
    """Tests for _matches_service branch coverage."""

    def test_matches_exact_product_match(self) -> None:
        """_matches_service returns 1.0 confidence for exact product match."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-44228",
            vendor_project="Apache Foundation",  # Vendor doesn't match
            product="Log4j",  # Exact product match
            vulnerability_name="Log4j RCE",
            date_added="2021-12-10",
            short_description="desc",
            required_action="patch",
            due_date="2021-12-24",
            notes="",
        )

        matches, confidence = source._matches_service(entry, "log4j", "1.0")
        assert matches is True
        assert confidence == 1.0  # Exact product match = 1.0

    def test_matches_substring_vendor_only(self) -> None:
        """_matches_service returns 0.7 confidence for substring vendor-only match."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource, KevEntry

        source = CisaKevSource()
        entry = KevEntry(
            cve_id="CVE-2021-41773",
            vendor_project="Apache Foundation",  # Contains "apache" substring
            product="HTTP Server",  # Doesn't contain "apache"
            vulnerability_name="Path Traversal",
            date_added="2021-11-03",
            short_description="desc",
            required_action="patch",
            due_date="2021-11-17",
            notes="",
        )

        # Query "apache" - matches vendor substring only (not product, not exact)
        matches, confidence = source._matches_service(entry, "apache", "2.4.49")
        assert matches is True
        assert confidence == 0.7  # Substring vendor-only match = 0.7


# =============================================================================
# Phase 4: Module Exports Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestModuleExports:
    """Tests for module export configuration (Task 4.1)."""

    def test_cisa_kev_source_importable_from_sources(self) -> None:
        """from cyberred.intelligence.sources import CisaKevSource works."""
        from cyberred.intelligence.sources import CisaKevSource

        assert CisaKevSource is not None

    def test_kev_catalog_importable_from_sources(self) -> None:
        """from cyberred.intelligence.sources import KevCatalog works."""
        from cyberred.intelligence.sources import KevCatalog

        assert KevCatalog is not None

    def test_kev_entry_importable_from_sources(self) -> None:
        """from cyberred.intelligence.sources import KevEntry works."""
        from cyberred.intelligence.sources import KevEntry

        assert KevEntry is not None
