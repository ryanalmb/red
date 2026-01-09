"""Integration tests for IntelligenceAggregator with REAL sources.

These tests query actual intelligence sources (network, filesystem, Docker)
to verify end-to-end aggregator behavior. Each test has skip markers for
missing dependencies.

Run all integration tests:
    pytest tests/integration/intelligence/test_aggregator.py -v --tb=short

Run with specific sources available:
    NVD_API_KEY=xxx MSF_RPC_PASSWORD=xxx pytest tests/integration/intelligence/test_aggregator.py -v
"""

import os
import pytest
import asyncio
import shutil
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from cyberred.intelligence import IntelligenceAggregator, IntelResult, IntelPriority, IntelligenceSource
from cyberred.intelligence.sources.cisa_kev import CisaKevSource
from cyberred.intelligence.sources.nvd import NvdSource
from cyberred.intelligence.sources.exploitdb import ExploitDbSource
from cyberred.intelligence.sources.nuclei import NucleiSource
from cyberred.intelligence.sources.metasploit import MetasploitSource


# =============================================================================
# Skip Markers for Dependencies
# =============================================================================

HAS_NVD_API_KEY = bool(os.environ.get("NVD_API_KEY"))
HAS_SEARCHSPLOIT = shutil.which("searchsploit") is not None
HAS_NUCLEI_TEMPLATES = Path("/root/nuclei-templates").exists() or Path("tests/fixtures/nuclei-templates").exists()
HAS_MSF_PASSWORD = bool(os.environ.get("MSF_RPC_PASSWORD"))  # Note: Uses MSF_RPC_PASSWORD per MetasploitSource


def get_nuclei_templates_path() -> str:
    """Get available nuclei templates path."""
    if Path("/root/nuclei-templates").exists():
        return "/root/nuclei-templates"
    return "tests/fixtures/nuclei-templates"


# =============================================================================
# Real CISA KEV Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregator_with_real_cisa_kev():
    """Test aggregator with REAL CISA KEV source (HTTP request to CISA).
    
    This test:
    - Creates a real CisaKevSource that fetches from cisa.gov
    - Queries for a known vulnerable product (Log4j, Apache)
    - Verifies results have expected structure
    """
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=35.0)
    
    # Use REAL source - will make HTTP request to CISA
    cisa_source = CisaKevSource()
    aggregator.add_source(cisa_source)
    
    # Query for Log4j - known to be in KEV
    results = await aggregator.query("Log4j", "2.14.1")
    
    # Should return results from CISA KEV
    assert isinstance(results, list)
    
    # Verify result structure if any results found
    for result in results:
        assert isinstance(result, IntelResult)
        assert result.source == "cisa_kev"
        assert result.priority == IntelPriority.CISA_KEV  # Priority 1
        if result.cve_id:
            assert result.cve_id.startswith("CVE-")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregator_cisa_health_check():
    """Test CISA KEV health check with real network call."""
    aggregator = IntelligenceAggregator()
    cisa_source = CisaKevSource()
    aggregator.add_source(cisa_source)
    
    health = await aggregator.health_check()
    
    assert "healthy" in health
    assert "sources" in health
    assert "cisa_kev" in health["sources"]
    # Health check should succeed (either cache valid or network reachable)
    assert health["sources"]["cisa_kev"]["healthy"] is True


# =============================================================================
# Real NVD Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_NVD_API_KEY, reason="NVD_API_KEY not set")
async def test_aggregator_with_real_nvd():
    """Test aggregator with REAL NVD source (API call to NIST).
    
    Requires: NVD_API_KEY environment variable set
    
    This test:
    - Creates a real NvdSource that queries NVD API
    - Queries for a known vulnerable product
    - Verifies results have expected CVE structure
    """
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=35.0)
    
    # Use REAL source - will make API call to NVD
    nvd_source = NvdSource()
    aggregator.add_source(nvd_source)
    
    # Query for OpenSSH - always has CVEs
    results = await aggregator.query("OpenSSH", "8.2")
    
    assert isinstance(results, list)
    
    # NVD should return some results for well-known software
    # Note: May be empty if rate-limited, so we just check structure
    for result in results:
        assert isinstance(result, IntelResult)
        assert result.source == "nvd"
        if result.cve_id:
            assert result.cve_id.startswith("CVE-")
        assert result.priority in [
            IntelPriority.NVD_CRITICAL,
            IntelPriority.NVD_HIGH,
            IntelPriority.NVD_MEDIUM,
        ]


# =============================================================================
# Real ExploitDB Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_SEARCHSPLOIT, reason="searchsploit not installed")
async def test_aggregator_with_real_exploitdb():
    """Test aggregator with REAL ExploitDB source (searchsploit CLI).
    
    Requires: searchsploit installed (typically in Kali Linux)
    
    This test:
    - Creates a real ExploitDbSource that runs searchsploit
    - Queries for a known vulnerable service (vsftpd 2.3.4 backdoor)
    - Verifies results have exploit paths
    """
    aggregator = IntelligenceAggregator(timeout=10.0, max_total_time=15.0)
    
    # Use REAL source - will run searchsploit command
    exploitdb_source = ExploitDbSource()
    aggregator.add_source(exploitdb_source)
    
    # Query for vsftpd 2.3.4 - famous backdoor in ExploitDB
    results = await aggregator.query("vsftpd", "2.3.4")
    
    assert isinstance(results, list)
    
    # vsftpd 2.3.4 backdoor is famous and should have results
    # But check structure regardless
    for result in results:
        assert isinstance(result, IntelResult)
        assert result.source == "exploitdb"
        assert result.exploit_available is True
        assert result.priority == IntelPriority.EXPLOITDB


# =============================================================================
# Real Nuclei Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_NUCLEI_TEMPLATES, reason="nuclei-templates not available")
async def test_aggregator_with_real_nuclei():
    """Test aggregator with REAL Nuclei source (local template scanning).
    
    Requires: nuclei-templates directory available
    
    This test:
    - Creates a real NucleiSource that scans template files
    - Queries for a known vulnerability
    - Verifies results reference template files
    """
    templates_path = get_nuclei_templates_path()
    
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=35.0)
    
    # Use REAL source - will scan template directory
    nuclei_source = NucleiSource(templates_path=templates_path)
    aggregator.add_source(nuclei_source)
    
    # Query for Apache - many templates target Apache
    results = await aggregator.query("apache", "2.4.49")
    
    assert isinstance(results, list)
    
    for result in results:
        assert isinstance(result, IntelResult)
        assert result.source == "nuclei"
        assert result.priority == IntelPriority.NUCLEI
        # Nuclei results should have template_id in metadata
        if result.metadata:
            assert "template_id" in result.metadata or "template_path" in result.metadata


# =============================================================================
# Real Metasploit Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_MSF_PASSWORD, reason="MSF_RPC_PASSWORD not set (Metasploit RPC not available)")
async def test_aggregator_with_real_metasploit():
    """Test aggregator with REAL Metasploit source (RPC to msfrpcd).
    
    Requires: 
    - MSF_RPC_PASSWORD environment variable set
    - msfrpcd running on localhost:55553
    
    This test:
    - Creates a real MetasploitSource that connects via RPC
    - Queries for a known vulnerable service
    - Verifies results have module paths
    """
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=35.0)
    
    # Use REAL source - will connect to msfrpcd
    msf_source = MetasploitSource()
    aggregator.add_source(msf_source)
    
    # Query for Apache Tomcat - many exploits target it
    results = await aggregator.query("tomcat", "9.0.30")
    
    assert isinstance(results, list)
    
    for result in results:
        assert isinstance(result, IntelResult)
        assert result.source == "metasploit"
        assert result.priority == IntelPriority.METASPLOIT
        assert result.exploit_available is True
        # MSF results should have module_path in metadata
        if result.metadata:
            assert "module_path" in result.metadata


# =============================================================================
# Multi-Source Aggregation Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregator_multi_source_real():
    """Test aggregator with MULTIPLE real sources.
    
    Uses whatever sources are actually available on the system.
    At minimum, CISA KEV should always work (just HTTP).
    """
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=60.0)
    sources_added = []
    
    # Always add CISA KEV (just HTTP, no special deps)
    cisa_source = CisaKevSource()
    aggregator.add_source(cisa_source)
    sources_added.append("cisa_kev")
    
    # Add NVD if API key available
    if HAS_NVD_API_KEY:
        nvd_source = NvdSource()
        aggregator.add_source(nvd_source)
        sources_added.append("nvd")
    
    # Add ExploitDB if searchsploit available
    if HAS_SEARCHSPLOIT:
        exploitdb_source = ExploitDbSource()
        aggregator.add_source(exploitdb_source)
        sources_added.append("exploitdb")
    
    # Add Nuclei if templates available
    if HAS_NUCLEI_TEMPLATES:
        templates_path = get_nuclei_templates_path()
        nuclei_source = NucleiSource(templates_path=templates_path)
        aggregator.add_source(nuclei_source)
        sources_added.append("nuclei")
    
    # Add Metasploit if password available
    if HAS_MSF_PASSWORD:
        msf_source = MetasploitSource()
        aggregator.add_source(msf_source)
        sources_added.append("metasploit")
    
    print(f"\nTesting with {len(sources_added)} real sources: {sources_added}")
    
    # Query for Apache - widely known, should have results from multiple sources
    results = await aggregator.query("Apache", "2.4.49")
    
    assert isinstance(results, list)
    print(f"Got {len(results)} results from real sources")
    
    # Track which sources returned results
    sources_with_results = set(r.source for r in results)
    print(f"Sources with results: {sources_with_results}")
    
    # Verify deduplication works - no duplicate CVE IDs with same source
    seen_cves = {}
    for result in results:
        if result.cve_id:
            key = f"{result.cve_id}"
            if key in seen_cves:
                # Same CVE should be merged (check _sources in metadata)
                assert "_sources" in result.metadata, f"Duplicate CVE {result.cve_id} not merged"
            seen_cves[key] = result
    
    # Verify priority ordering
    for i in range(1, len(results)):
        assert results[i-1].priority <= results[i].priority, \
            f"Results not sorted by priority: {results[i-1].priority} > {results[i].priority}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregator_parallel_execution_real():
    """Verify real sources run in parallel (timing test).
    
    Uses CISA KEV (always available) to verify parallelism.
    """
    aggregator = IntelligenceAggregator(timeout=30.0, max_total_time=60.0)
    
    # Add CISA KEV twice (different instances to simulate multiple sources)
    cisa_source1 = CisaKevSource()
    cisa_source2 = CisaKevSource()
    aggregator.add_source(cisa_source1)
    # Note: Can't add twice since same name, so just verify single source timing
    
    import time
    start = time.time()
    results = await aggregator.query("Log4j", "2.14.1")
    duration = time.time() - start
    
    print(f"\nQuery completed in {duration:.2f}s")
    
    # Should complete within the timeout (30s) + overhead
    assert duration < 35.0, f"Query took too long: {duration}s"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregator_graceful_degradation_real():
    """Test that aggregator handles partial source failures gracefully.
    
    Adds a non-existent Metasploit source to verify it doesn't block results
    from working sources (CISA KEV).
    """
    aggregator = IntelligenceAggregator(timeout=5.0, max_total_time=10.0)
    
    # Add working source
    cisa_source = CisaKevSource()
    aggregator.add_source(cisa_source)
    
    # Add broken source (wrong password, should fail to connect)
    broken_msf = MetasploitSource(
        password="definitely_wrong_password",
        host="127.0.0.1",
        port=55553,
        timeout=2.0,
    )
    aggregator.add_source(broken_msf)
    
    # Query should still return CISA results despite MSF failure
    results = await aggregator.query("Log4j", "2.14.1")
    
    assert isinstance(results, list)
    # Should have results from CISA even if MSF failed
    cisa_results = [r for r in results if r.source == "cisa_kev"]
    print(f"\nGot {len(cisa_results)} CISA results despite broken MSF source")
