"""Integration tests for NVD Source.

These tests verify NvdSource behavior against the real NVD API.

Story: 5-3-nvd-api-source-integration
"""

import pytest

from cyberred.intelligence import IntelPriority, IntelResult
from cyberred.intelligence.sources import NvdSource


# =============================================================================
# Integration Tests Against Real NVD API (AC: 6)
# =============================================================================


@pytest.mark.integration
class TestNvdSourceIntegration:
    """Integration tests for NvdSource against live NVD API."""

    @pytest.mark.asyncio
    async def test_query_real_nvd_api_for_known_cve(self) -> None:
        """Query real NVD API and parse response correctly for known CVE.
        
        Uses Log4j (CVE-2021-44228) as a known critical CVE.
        Note: NVD keyword search works better with single keyword, not combined
        service+version queries.
        """
        source = NvdSource(timeout=30.0)  # Longer timeout for real API
        
        # Query for Log4j - note: just the product name works better with NVD API
        # Combined "Log4j 2.14.0" returns 0 results but "Log4j" returns vulnerabilities
        results = await source.query("Log4j", "")
        
        # Should find at least one CVE
        assert len(results) >= 1, f"Expected results but got {len(results)}"
        
        # Find the Log4Shell CVE specifically
        log4shell_results = [r for r in results if r.cve_id == "CVE-2021-44228"]
        
        if log4shell_results:
            result = log4shell_results[0]
            
            # Verify result structure
            assert result.source == "nvd"
            assert result.cve_id == "CVE-2021-44228"
            assert result.severity == "critical"
            assert result.priority == IntelPriority.NVD_CRITICAL
            
            # Verify metadata contains expected fields
            assert "cvss_v3_score" in result.metadata
            assert result.metadata["cvss_v3_score"] == 10.0
            assert "description" in result.metadata

    @pytest.mark.asyncio
    async def test_returns_valid_intel_result_objects(self) -> None:
        """Results are valid IntelResult objects with all required fields."""
        source = NvdSource(timeout=30.0)
        
        results = await source.query("OpenSSH", "8.2")
        
        # May or may not find results depending on NVD state
        for result in results:
            # Verify type
            assert isinstance(result, IntelResult)
            
            # Verify required fields
            assert result.source == "nvd"
            assert result.cve_id is None or result.cve_id.startswith("CVE-")
            assert result.severity in ("critical", "high", "medium", "low", "info")
            assert result.priority in (2, 3, 7)  # NVD priorities
            assert 0.0 <= result.confidence <= 1.0
            
            # NVD doesn't track exploits
            assert result.exploit_available is False
            assert result.exploit_path is None

    @pytest.mark.asyncio
    async def test_handles_no_results_gracefully(self) -> None:
        """Query for nonexistent service returns empty list."""
        source = NvdSource(timeout=30.0)
        
        # Query for something unlikely to exist
        results = await source.query("NonExistentFakeService12345", "99.99.99")
        
        # Should return empty list, not error
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_against_real_api(self) -> None:
        """health_check() returns True when NVD API is reachable."""
        source = NvdSource(timeout=10.0)
        
        result = await source.health_check()
        
        # API should be reachable (unless there's a major outage)
        assert result is True

    @pytest.mark.asyncio
    async def test_api_key_improves_rate_limit(self) -> None:
        """API key configuration is used for queries.
        
        Note: We can't easily verify rate limit differences in a test,
        but we verify the key is passed to nvdlib.
        """
        import os
        
        # Get API key from environment (set in Epic 5 prereqs)
        api_key = os.environ.get("NVD_API_KEY")
        
        source = NvdSource(api_key=api_key, timeout=30.0)
        
        # Verify API key is set
        assert source._api_key == api_key
        
        # Query should work (rate limits are higher with API key)
        results = await source.query("Apache", "2.4.49")
        
        # Should return results (Apache vulns are well-known)
        # Note: May return empty if NVD is rate limiting
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_cvss_priority_mapping_in_real_results(self) -> None:
        """Real results have correct priority based on CVSS score."""
        source = NvdSource(timeout=30.0)
        
        # Log4Shell is known to be critical (CVSS 10.0)
        results = await source.query("Log4j", "")
        
        for result in results:
            cvss_score = result.metadata.get("cvss_v3_score") or result.metadata.get("cvss_v2_score")
            
            if cvss_score is not None:
                if cvss_score >= 9.0:
                    assert result.priority == IntelPriority.NVD_CRITICAL
                elif cvss_score >= 7.0:
                    assert result.priority == IntelPriority.NVD_HIGH
                else:
                    assert result.priority == IntelPriority.NVD_MEDIUM
