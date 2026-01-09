import pytest
import unittest.mock
from dataclasses import is_dataclass
from cyberred.intelligence.sources.metasploit import MsfModuleEntry, MetasploitSource
from cyberred.intelligence.base import IntelligenceSource, IntelPriority

@pytest.mark.unit
class TestMsfModuleEntry:
    def test_msf_module_entry_structure(self):
        """Test MsfModuleEntry dataclass structure."""
        assert is_dataclass(MsfModuleEntry)
        
        entry = MsfModuleEntry(
            module_path="exploit/linux/http/test_module",
            name="Test Module",
            rank="excellent",
            disclosure_date="2023-01-01",
            cve_ids=["CVE-2023-1234"],
            description="Test description",
            platform="linux",
            arch="x86",
            ref_names=["CVE-2023-1234"]
        )
        
        assert entry.module_path == "exploit/linux/http/test_module"
        assert entry.name == "Test Module"
        assert entry.rank == "excellent"
        assert entry.disclosure_date == "2023-01-01"
        assert entry.cve_ids == ["CVE-2023-1234"]
        assert entry.description == "Test description"
        assert entry.platform == "linux"
        assert entry.arch == "x86"
        assert entry.ref_names == ["CVE-2023-1234"]

    def test_from_rpc_result_parsing(self):
        """Test parsing of RPC module info."""
        rpc_info = {
            "name": "Apache Struts 2 REST XStream",
            "rank": "excellent",
            "disclosure_date": "2017-09-05",
            "description": "RCE in Struts",
            "platform": ["linux", "windows"],
            "arch": ["java"],
            "references": [
                ["CVE", "2017-9805"],
                ["URL", "http://struts.apache.org"]
            ]
        }
        
        entry = MsfModuleEntry.from_rpc_result("exploit/multi/http/struts2_rest_xstream", rpc_info)
        
        assert entry.module_path == "exploit/multi/http/struts2_rest_xstream"
        assert entry.name == "Apache Struts 2 REST XStream"
        assert entry.rank == "excellent"
        assert entry.cve_ids == ["CVE-2017-9805"]
        assert "linux,windows" in entry.platform  # Order might vary so check containment if not sorted
        assert entry.arch == "java"
        assert "CVE-2017-9805" in entry.ref_names

    def test_from_rpc_result_defaults(self):
        """Test handling of missing fields in RPC result."""
        rpc_info = {}
        
        entry = MsfModuleEntry.from_rpc_result("exploit/test/missing_fields", rpc_info)
        
        assert entry.module_path == "exploit/test/missing_fields"
        assert entry.name == "missing_fields"  # Should default to basename
        assert entry.rank == "normal"
        assert entry.cve_ids == []
        assert entry.platform == ""

@pytest.mark.unit
class TestMetasploitSource:
    def test_inheritance(self):
        """Test MetasploitSource inherits from IntelligenceSource."""
        source = MetasploitSource(password="test")
        assert isinstance(source, IntelligenceSource)
        assert source.name == "metasploit"
        
    def test_priority(self):
        """Test source priority is METASPLOIT (4)."""
        source = MetasploitSource(password="test")
        assert source.priority == IntelPriority.METASPLOIT
        assert source.priority == 4
        
    def test_initialization_defaults(self):
        """Test initialization with default values."""
        source = MetasploitSource(password="test")
        assert source._host == "127.0.0.1"
        assert source._port == 55553
        # We might check ssl default too, depending on what we decided

    def test_get_client_connects(self):
        """Test _get_client connects to RPC."""
        source = MetasploitSource(password="test", ssl=False)
        
        with unittest.mock.patch("cyberred.intelligence.sources.metasploit.MsfRpcClient") as mock_client_cls:
            mock_client_cls.return_value = unittest.mock.Mock()
            
            client = source._get_client()
            
            assert client is not None
            mock_client_cls.assert_called_once_with(
                password="test",
                server="127.0.0.1",
                port=55553,
                ssl=False
            )
            assert source._client == client

    def test_get_client_reuses_connection(self):
        """Test _get_client reuses existing connection."""
        source = MetasploitSource(password="test")
        mock_client = unittest.mock.Mock()
        source._client = mock_client
        
        with unittest.mock.patch("cyberred.intelligence.sources.metasploit.MsfRpcClient") as mock_client_cls:
            client = source._get_client()
            assert client == mock_client
            mock_client_cls.assert_not_called()

    def test_get_client_connection_error(self):
        """Test _get_client raises exception on failure."""
        source = MetasploitSource(password="test")
        
        with unittest.mock.patch("cyberred.intelligence.sources.metasploit.MsfRpcClient", side_effect=Exception("Auth failed")):
            with pytest.raises(Exception):
                source._get_client()

@pytest.mark.unit
class TestMetasploitQuery:
    @pytest.mark.asyncio
    async def test_query_returns_results(self):
        """Test query returns matching modules."""
        source = MetasploitSource(password="test")
        
        # Mock results from _search_modules
        mock_entry = MsfModuleEntry(
            module_path="exploit/test",
            name="Test Exploit",
            rank="excellent",
            disclosure_date="2023-01-01",
            cve_ids=["CVE-2023-1234"],
            platform="linux",
            ref_names=["CVE-2023-1234"]
        )
        
        with unittest.mock.patch.object(source, "_search_modules", return_value=[mock_entry]):
            results = await source.query("test", "1.0")
            
            assert len(results) == 1
            assert results[0].source == "metasploit"
            assert results[0].cve_id == "CVE-2023-1234"
            assert results[0].severity == "critical" # excellent -> critical
            assert results[0].exploit_available is True
            assert results[0].exploit_path == "exploit/test"

    @pytest.mark.asyncio
    async def test_query_handles_error(self):
        """Test query returns empty list on error."""
        source = MetasploitSource(password="test")
        
        with unittest.mock.patch.object(source, "_search_modules", side_effect=Exception("RPC Error")):
            results = await source.query("test", "1.0")
            assert results == []

    @pytest.mark.asyncio
    async def test_rank_mapping(self):
        """Test rank to severity mapping."""
        source = MetasploitSource(password="test")
        assert source._rank_to_severity("excellent") == "critical"
        assert source._rank_to_severity("great") == "high"
        assert source._rank_to_severity("good") == "high"
        assert source._rank_to_severity("normal") == "medium"
        assert source._rank_to_severity("average") == "medium"
        assert source._rank_to_severity("low") == "low"
        assert source._rank_to_severity("manual") == "low"
        assert source._rank_to_severity("unknown") == "medium" # default

    def test_search_modules(self):
        """Test _search_modules queries RPC."""
        source = MetasploitSource(password="test")
        
        # Mock client and modules
        mock_client = unittest.mock.Mock()
        mock_client.modules.exploits = ["exploit/linux/http/tomcat_mgr_deploy", "exploit/other"]
        mock_client.modules.auxiliary = []
        
        # Mock modules.use()
        mock_info = {
            "name": "Tomcat Manager Application Deployer",
            "rank": "excellent",
            "disclosure_date": "2009-11-09",
            "description": "Deploy a payload...",
            "platform": ["linux"],
            "arch": ["java"],
            "references": [["CVE", "2009-3548"]]
        }
        mock_client.modules.use.return_value = mock_info
        
        with unittest.mock.patch.object(source, "_get_client", return_value=mock_client):
            entries = source._search_modules("tomcat", "manager")
            
            assert len(entries) == 1
            assert entries[0].module_path == "exploit/linux/http/tomcat_mgr_deploy"
            assert entries[0].name == "Tomcat Manager Application Deployer"

    def test_search_matches(self):
        """Test _matches_search logic."""
        source = MetasploitSource(password="test")
        assert source._matches_search("exploit/linux/http/tomcat_mgr_deploy", "tomcat manager") is True
        assert source._matches_search("exploit/linux/http/tomcat_mgr_deploy", "apache") is False

    def test_from_rpc_result_object_info(self):
        """Test parsing of RPC result when info is an object (not dict)."""
        # Mock object with attributes instead of dict
        class MockModuleInfo:
            name = "Object Module"
            rank = "good"
            disclosure_date = "2022-05-15"
            description = "From object"
            platform = "windows"
            arch = "x64"
            references = [["CVE", "2022-1234"]]
        
        entry = MsfModuleEntry.from_rpc_result("exploit/test/object_module", MockModuleInfo())
        
        assert entry.name == "Object Module"
        assert entry.rank == "good"
        assert entry.platform == "windows"
        assert entry.cve_ids == ["CVE-2022-1234"]

    def test_from_rpc_result_datetime_disclosure_date(self):
        """Test handling of non-string disclosure_date (e.g., datetime or int)."""
        from datetime import date
        rpc_info = {
            "name": "Test Module",
            "rank": "normal",
            "disclosure_date": date(2023, 6, 15),  # Not a string
            "references": []
        }
        
        entry = MsfModuleEntry.from_rpc_result("exploit/test/datetime_date", rpc_info)
        
        assert entry.disclosure_date == "2023-06-15"
        assert isinstance(entry.disclosure_date, str)

    def test_from_rpc_result_none_disclosure_date(self):
        """Test handling of None disclosure_date."""
        rpc_info = {
            "name": "Test Module",
            "rank": "normal",
            "disclosure_date": None,
            "references": []
        }
        
        entry = MsfModuleEntry.from_rpc_result("exploit/test/none_date", rpc_info)
        
        assert entry.disclosure_date == ""

    def test_search_modules_module_list_error(self):
        """Test _search_modules handles module list errors gracefully."""
        source = MetasploitSource(password="test")
        
        mock_client = unittest.mock.Mock()
        # Make accessing exploits raise an exception
        type(mock_client.modules).exploits = unittest.mock.PropertyMock(side_effect=Exception("List error"))
        type(mock_client.modules).auxiliary = unittest.mock.PropertyMock(side_effect=Exception("List error"))
        
        with unittest.mock.patch.object(source, "_get_client", return_value=mock_client):
            entries = source._search_modules("test", "1.0")
            
            # Should return empty list, not raise
            assert entries == []

    def test_search_modules_module_info_error(self):
        """Test _search_modules handles module info errors gracefully."""
        source = MetasploitSource(password="test")
        
        mock_client = unittest.mock.Mock()
        # Return a matching module path
        mock_client.modules.exploits = ["exploit/test/matching_module"]
        mock_client.modules.auxiliary = []
        # But fail when getting module info
        mock_client.modules.use.side_effect = Exception("Info retrieval failed")
        
        with unittest.mock.patch.object(source, "_get_client", return_value=mock_client):
            entries = source._search_modules("test", "1.0")
            
            # Should return empty list (module was filtered out due to error)
            assert entries == []

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health_check returns True when connection succeeds."""
        source = MetasploitSource(password="test")
        
        # Mock successful _get_client
        mock_client = unittest.mock.Mock()
        with unittest.mock.patch.object(source, "_get_client", return_value=mock_client):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health_check returns False when connection fails."""
        source = MetasploitSource(password="test")
        
        # Mock _get_client to raise exception
        with unittest.mock.patch.object(source, "_get_client", side_effect=Exception("Connection refused")):
            result = await source.health_check()
            assert result is False
