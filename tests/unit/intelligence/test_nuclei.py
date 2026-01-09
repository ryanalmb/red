import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from cyberred.intelligence.sources.nuclei import NucleiTemplate, NucleiSource

from cyberred.intelligence.base import IntelligenceSource, IntelPriority

@pytest.mark.unit
class TestNucleiTemplate:
    """Tests for NucleiTemplate dataclass."""

    def test_nuclei_template_fields(self):
        """Test that NucleiTemplate has all required fields."""
        template = NucleiTemplate(
            template_id="test-id",
            name="Test Template",
            severity="high",
            tags=["cve", "rce"],
            cve_ids=["CVE-2021-1234"],
            category="cve",
            path="cves/test.yaml",
            author="tester",
            description="A test template"
        )
        
        assert template.template_id == "test-id"
        assert template.name == "Test Template"
        assert template.severity == "high"
        assert template.tags == ["cve", "rce"]
        assert template.cve_ids == ["CVE-2021-1234"]
        assert template.category == "cve"
        assert template.path == "cves/test.yaml"
        assert template.author == "tester"
        assert template.description == "A test template"

    @patch("builtins.open", new_callable=mock_open, read_data="""
id: yaml-id
info:
  name: Yaml Template
  severity: critical
  tags: cve,test
  classification:
    cve-id: CVE-2022-5678
""")
    @patch("yaml.safe_load")
    def test_from_yaml_parsing(self, mock_yaml, mock_file):
        """Test parsing of Nuclei YAML content."""
        mock_yaml.return_value = {
            "id": "yaml-id",
            "info": {
                "name": "Yaml Template",
                "severity": "critical",
                "tags": "cve,test",
                "classification": {
                    "cve-id": "CVE-2022-5678"
                }
            }
        }
        
        template = NucleiTemplate.from_yaml(Path("test.yaml"), Path("."))
        
        assert template.template_id == "yaml-id"
        assert template.name == "Yaml Template"
        assert template.severity == "critical"
        assert template.cve_ids == ["CVE-2022-5678"]
        assert template.tags == ["cve", "test"]

    @patch("builtins.open", new_callable=mock_open, read_data="id: missing-optional\\ninfo:\\n  name: Missing Optional")
    @patch("yaml.safe_load")
    def test_from_yaml_missing_optional(self, mock_yaml, mock_file):
        """Test parsing with missing optional fields."""
        mock_yaml.return_value = {
            "id": "missing-optional",
            "info": {
                "name": "Missing Optional"
                # Missing tags, severity, classification
            }
        }
        
        template = NucleiTemplate.from_yaml(Path("test.yaml"), Path("."))
        
        assert template.template_id == "missing-optional"
        assert template.severity == "info" # Default
        assert template.tags == []
        assert template.cve_ids == [] 

@pytest.mark.unit
class TestNucleiSourceBase:
    """Tests for NucleiSource base functionality."""

    def test_inheritance(self):
        """Test that NucleiSource inherits from IntelligenceSource."""
        assert issubclass(NucleiSource, IntelligenceSource)

    def test_nuclei_source_initialization(self):
        """Test that NucleiSource initializes correctly."""
        source = NucleiSource()
        assert source.name == "nuclei"
        assert source.priority == IntelPriority.NUCLEI

    @patch("pathlib.Path.rglob")
    @patch("cyberred.intelligence.sources.nuclei.NucleiTemplate.from_yaml")
    def test_build_index(self, mock_from_yaml, mock_rglob):
        """Test index building scans templates and builds map."""
        source = NucleiSource(templates_path="/tmp/test")
        
        # Mock template files
        mock_rglob.return_value = [Path("/tmp/test/t1.yaml"), Path("/tmp/test/t2.yaml")]
        
        # Mock template parsing
        t1 = Mock(spec=NucleiTemplate)
        t1.template_id = "test-1"
        t1.name = "Test One"
        t1.tags = ["tag1"]
        t1.cve_ids = []
        t1.category = "other"
        
        t2 = Mock(spec=NucleiTemplate)
        t2.template_id = "test-2"
        t2.name = "Test Two cve"
        t2.tags = ["tag2"]
        t2.cve_ids = ["CVE-2021-9999"]
        t2.category = "cve"
        
        mock_from_yaml.side_effect = [t1, t2]
        
        # Build index
        index = source._build_index()
        
        # Check keywords
        assert "test-1" in index
        assert "test" in index # From "Test One" split
        assert "one" in index
        assert "tag1" in index
        
        assert "test-2" in index
        assert "cve-2021-9999" in index
        
        # Check values
        assert t1 in index["test-1"]
        assert t2 in index["test-2"]

    def test_extract_keywords(self):
        """Test keyword extraction logic."""
        source = NucleiSource()
        template = Mock(spec=NucleiTemplate)
        template.template_id = "Test-ID"
        template.name = "Name With Words"
        template.tags = ["Tag1", "Tag2"]
        template.cve_ids = ["CVE-1234"]
        template.category = "Category"
        
        keywords = source._extract_keywords(template)
        
        expected = {
            "test-id", "name", "with", "words",
            "tag1", "tag2", "cve-1234", "category"
        }
        assert expected.issubset(keywords)

    def test_to_intel_result(self):
        """Test conversion to IntelResult."""
        source = NucleiSource(templates_path="/tmp")
        template = NucleiTemplate(
            template_id="test-id",
            name="Test Template",
            severity="critical",
            tags=["cve", "rce"],
            cve_ids=["CVE-2021-1234"],
            category="cve",
            path="path/to/template.yaml",
            author="tester",
            description="desc"
        )
        
        result = source._to_intel_result(template)
        
        assert result.source == "nuclei"
        assert result.cve_id == "CVE-2021-1234"
        assert result.severity == "critical"
        assert result.exploit_available is True # rce tag
        assert result.priority == 5
        assert result.metadata["template_id"] == "test-id"
        assert result.metadata["tags"] == ["cve", "rce"]

    @pytest.mark.asyncio
    @patch("cyberred.intelligence.sources.nuclei.NucleiSource._build_index")
    async def test_query(self, mock_build_index):
        """Test query logic."""
        source = NucleiSource()
        
        # Mock index
        t1 = NucleiTemplate(
            template_id="wp-login",
            name="WordPress Login",
            severity="info",
            tags=["wordpress"],
            cve_ids=[],
            category="default-login",
            path="wp.yaml"
        )
        source._index = {
            "wordpress": [t1],
            "login": [t1]
        }
        
        # Test query
        results = await source.query("WordPress", "5.8")
        
        assert len(results) == 1
        assert results[0].metadata["template_id"] == "wp-login"
        
        # Test caching - should not call build_index if index exists
        mock_build_index.assert_not_called()
        
        # Test lazy loading
        source._index = None
        mock_build_index.return_value = {"wordpress": [t1]}
        
        results = await source.query("WordPress", "")
        mock_build_index.assert_called_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check logic."""
        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.is_dir") as mock_is_dir, \
             patch("pathlib.Path.rglob") as mock_rglob:
            
            source = NucleiSource()
            
            # Case 1: All good
            mock_exists.return_value = True
            mock_is_dir.return_value = True
            mock_rglob.return_value = [Path("t1.yaml")]
            assert await source.health_check() is True
            
            # Case 2: No directory
            mock_exists.return_value = False
            assert await source.health_check() is False 
            
            # Case 3: Empty directory
            mock_exists.return_value = True
            mock_is_dir.return_value = True
            mock_rglob.return_value = [] # Empty generator
            assert await source.health_check() is False

            # Case 4: Not a directory (is_dir=False)
            mock_exists.return_value = True
            mock_is_dir.return_value = False
            assert await source.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health_check exception handling."""
        source = NucleiSource()
        
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = PermissionError("Access denied")
            assert await source.health_check() is False


@pytest.mark.unit
class TestNucleiTemplateCategories:
    """Tests for category determination logic."""

    def test_category_exposure(self):
        """Test exposure category detection."""
        category = NucleiTemplate._determine_category(["exposure", "info"])
        assert category == "exposure"

    def test_category_misconfiguration(self):
        """Test misconfiguration category detection (misconfig tag)."""
        category = NucleiTemplate._determine_category(["misconfig", "security"])
        assert category == "misconfiguration"

    def test_category_misconfiguration_full(self):
        """Test misconfiguration category detection (full tag)."""
        category = NucleiTemplate._determine_category(["misconfiguration", "headers"])
        assert category == "misconfiguration"

    def test_category_default_login(self):
        """Test default-login category detection."""
        category = NucleiTemplate._determine_category(["default-login", "admin"])
        assert category == "default-login"

    def test_category_cve_prefix(self):
        """Test CVE prefix category detection."""
        category = NucleiTemplate._determine_category(["cve-2021-44228", "rce"])
        assert category == "cve"

    def test_category_other(self):
        """Test default 'other' category."""
        category = NucleiTemplate._determine_category(["tech", "detection"])
        assert category == "other"


@pytest.mark.unit
class TestNucleiTemplateEdgeCases:
    """Tests for edge cases in NucleiTemplate parsing."""

    @patch("builtins.open", new_callable=mock_open, read_data="invalid")
    @patch("yaml.safe_load")
    def test_from_yaml_invalid_format(self, mock_yaml, mock_file):
        """Test ValueError on invalid template format (missing id/info)."""
        mock_yaml.return_value = {"not_id": "bad", "not_info": {}}
        
        with pytest.raises(ValueError, match="Invalid template format"):
            NucleiTemplate.from_yaml(Path("bad.yaml"), Path("."))

    @patch("builtins.open", new_callable=mock_open, read_data="invalid")
    @patch("yaml.safe_load")
    def test_from_yaml_none_data(self, mock_yaml, mock_file):
        """Test ValueError when YAML returns None."""
        mock_yaml.return_value = None
        
        with pytest.raises(ValueError, match="Invalid template format"):
            NucleiTemplate.from_yaml(Path("empty.yaml"), Path("."))

    @patch("builtins.open", new_callable=mock_open, read_data="valid")
    @patch("yaml.safe_load")
    def test_from_yaml_list_cve_ids(self, mock_yaml, mock_file):
        """Test parsing list of CVE IDs."""
        mock_yaml.return_value = {
            "id": "multi-cve",
            "info": {
                "name": "Multiple CVEs",
                "classification": {
                    "cve-id": ["CVE-2021-1111", "CVE-2021-2222", "CVE-2021-3333"]
                }
            }
        }
        
        template = NucleiTemplate.from_yaml(Path("multi.yaml"), Path("."))
        assert template.cve_ids == ["CVE-2021-1111", "CVE-2021-2222", "CVE-2021-3333"]

    @patch("builtins.open", new_callable=mock_open, read_data="valid")
    @patch("yaml.safe_load")
    def test_from_yaml_path_not_relative(self, mock_yaml, mock_file):
        """Test path fallback when relative_to fails."""
        mock_yaml.return_value = {
            "id": "external",
            "info": {"name": "External Template"}
        }
        
        # Use paths that can't be relative
        template = NucleiTemplate.from_yaml(
            Path("/other/path/template.yaml"), 
            Path("/root/templates")
        )
        # Should fall back to absolute path string
        assert "/other/path/template.yaml" in template.path


@pytest.mark.unit
class TestNucleiSourceErrorHandling:
    """Tests for error handling in NucleiSource."""

    @pytest.mark.asyncio
    async def test_query_exception_returns_empty(self):
        """Test that query returns empty list on exception."""
        source = NucleiSource()
        
        # Force an exception during index build
        with patch.object(source, '_build_index', side_effect=RuntimeError("Index failed")):
            results = await source.query("anything", "1.0")
            assert results == []

    @patch("pathlib.Path.rglob")
    def test_build_index_handles_parse_errors(self, mock_rglob):
        """Test _build_index continues on parse errors."""
        source = NucleiSource(templates_path="/tmp/test")
        
        mock_rglob.return_value = [
            Path("/tmp/test/good.yaml"),
            Path("/tmp/test/bad.yaml"),
        ]
        
        # First parse succeeds, second fails
        with patch.object(NucleiTemplate, 'from_yaml') as mock_from_yaml:
            good_template = Mock(spec=NucleiTemplate)
            good_template.template_id = "good"
            good_template.name = "Good"
            good_template.tags = []
            good_template.cve_ids = []
            good_template.category = "other"
            
            mock_from_yaml.side_effect = [
                good_template,
                ValueError("Bad YAML"),
            ]
            
            index = source._build_index()
            
            # Should have indexed the good template
            assert "good" in index
            # Bad template should have been skipped

    @patch("pathlib.Path.rglob")
    @patch("time.time")
    def test_build_index_slow_warning(self, mock_time, mock_rglob):
        """Test slow index warning is triggered."""
        source = NucleiSource(templates_path="/tmp/test")
        
        mock_rglob.return_value = []
        
        # Simulate 5 second build time (> 4.0s threshold)
        mock_time.side_effect = [0.0, 5.0]
        
        # Should complete but log warning internally
        index = source._build_index()
        assert index == {}
