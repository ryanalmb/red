"""Integration tests for CISA KEV Source.

Tests verify actual connectivity and parsing against the real CISA KEV feed.
These tests require network access to CISA servers.
"""

import pytest

from cyberred.intelligence import IntelPriority, IntelResult


@pytest.mark.integration
class TestCisaKevIntegration:
    """Integration tests against real CISA KEV feed."""

    @pytest.mark.asyncio
    async def test_fetch_real_cisa_kev_feed(self) -> None:
        """Integration: Fetches real CISA KEV feed successfully."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog

        catalog = KevCatalog()
        entries = await catalog.fetch()

        # KEV catalog should always have entries (currently ~1200+)
        assert len(entries) > 100, f"Expected 100+ entries, got {len(entries)}"

        # Check first entry has all required fields
        first_entry = entries[0]
        assert first_entry.cve_id.startswith("CVE-")
        assert first_entry.vendor_project != ""
        assert first_entry.product != ""
        assert first_entry.vulnerability_name != ""
        assert first_entry.date_added != ""
        assert first_entry.required_action != ""
        assert first_entry.due_date != ""

    @pytest.mark.asyncio
    async def test_parse_all_entries_without_error(self) -> None:
        """Integration: Parses all KEV entries without JSON/parsing errors."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog, KevEntry

        catalog = KevCatalog()
        entries = await catalog.fetch()

        # All entries should be valid KevEntry instances
        for entry in entries:
            assert isinstance(entry, KevEntry)
            assert entry.cve_id is not None
            assert entry.vendor_project is not None
            assert entry.product is not None

    @pytest.mark.asyncio
    async def test_query_returns_valid_intel_results(self) -> None:
        """Integration: Query for Apache returns valid IntelResult objects."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        results = await source.query("Apache", "2.4")

        # Apache has multiple KEV entries
        assert len(results) >= 1, "Expected at least 1 Apache CVE in KEV"

        # Verify result structure
        for result in results:
            assert isinstance(result, IntelResult)
            assert result.source == "cisa_kev"
            assert result.cve_id.startswith("CVE-")
            assert result.severity == "critical"
            assert result.exploit_available is True
            assert result.priority == IntelPriority.CISA_KEV

            # Verify metadata fields
            assert "vulnerability_name" in result.metadata
            assert "vendor_project" in result.metadata
            assert "date_added" in result.metadata

    @pytest.mark.asyncio
    async def test_query_log4j_returns_known_cve(self) -> None:
        """Integration: Query for Log4j returns CVE-2021-44228."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        results = await source.query("Log4j", "2.14")

        # Log4j CVE-2021-44228 should be in KEV
        cve_ids = [r.cve_id for r in results]
        assert "CVE-2021-44228" in cve_ids, f"Expected CVE-2021-44228 in {cve_ids}"

    @pytest.mark.asyncio
    async def test_health_check_with_real_feed(self) -> None:
        """Integration: health_check() returns True against real CISA feed."""
        from cyberred.intelligence.sources.cisa_kev import CisaKevSource

        source = CisaKevSource()
        result = await source.health_check()

        assert result is True, "CISA KEV should be healthy"

    @pytest.mark.asyncio
    async def test_cache_persistence(self, tmp_path) -> None:
        """Integration: Cache file persists and can be reloaded."""
        from cyberred.intelligence.sources.cisa_kev import KevCatalog
        from unittest.mock import patch, PropertyMock

        catalog = KevCatalog()
        cache_file = tmp_path / "kev_catalog.json"

        # Patch CACHE_FILE to use temp path
        with patch.object(type(catalog), "CACHE_FILE", new_callable=PropertyMock, return_value=cache_file):
            # Fetch and cache
            entries = await catalog.fetch()
            assert len(entries) > 100

            # Cache file should exist
            assert cache_file.exists()

            # Should be able to reload from cache
            cached_entries = catalog.load_cached()
            assert cached_entries is not None
            assert len(cached_entries) == len(entries)
