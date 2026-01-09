
import pytest
import shutil
from pathlib import Path
from cyberred.intelligence.sources.nuclei import NucleiSource, NucleiTemplate

@pytest.mark.integration
class TestNucleiIntegration:
    """Integration tests for NucleiSource using local fixtures."""
    
    @pytest.fixture
    def fixture_path(self):
        """Return path to fixture templates."""
        return Path("/root/red/tests/fixtures/nuclei-templates")

    @pytest.fixture
    async def source(self, fixture_path):
        """Return initialized NucleiSource using fixtures."""
        return NucleiSource(templates_path=str(fixture_path))

    @pytest.mark.asyncio
    async def test_query_cve_match(self, source):
        """Test querying by CVE keywords."""
        results = await source.query("log4j", "")
        
        assert len(results) >= 1
        found = False
        for res in results:
            if "CVE-2021-44228" in res.cve_id:
                found = True
                assert res.source == "nuclei"
                assert res.severity == "critical"
                assert res.priority == 5
                assert res.metadata["template_id"] == "CVE-2021-44228"
        
        assert found, "Log4j template not found in results"

    @pytest.mark.asyncio
    async def test_query_tech_match(self, source):
        """Test querying by technology name."""
        results = await source.query("WordPress", "")
        
        # Should find wordpress-detection at minimum
        assert len(results) >= 1
        ids = [r.metadata["template_id"] for r in results]
        assert "wordpress-detection" in ids

    @pytest.mark.asyncio
    async def test_query_no_match(self, source):
        """Test querying for non-existent term."""
        results = await source.query("NonExistentServiceLikely", "")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_parse_real_files(self, source):
        """Verify _build_index successfully parses all fixture files."""
        # This implicitly tests parsing logic against real files on disk
        index = source._build_index()
        
        # Verify specific expected entries
        assert "cve-2021-44228" in index
        assert "wordpress-detection" in index
        assert "http-missing-security-headers" in index
        
        # Verify structure
        for templates in index.values():
            for t in templates:
                assert isinstance(t, NucleiTemplate)
                assert t.path # Should have a path
