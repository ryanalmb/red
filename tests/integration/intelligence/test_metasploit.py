import pytest
import os
import asyncio
from cyberred.intelligence.sources.metasploit import MetasploitSource

@pytest.fixture
def msf_config():
    """Get MSF config from env or defaults."""
    return {
        "password": os.environ.get("MSF_RPC_PASSWORD", "cyber_red_msf_password"),
        "host": os.environ.get("MSF_RPC_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MSF_RPC_PORT", 55553)),
    }

@pytest.fixture
def msf_available(msf_config):
    """Check if Metasploit RPC is available."""
    # Simple TCP check using socket
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((msf_config["host"], msf_config["port"]))
        s.close()
        return True
    except Exception:
        return False

@pytest.mark.integration
class TestMetasploitIntegration:
    @pytest.mark.asyncio
    async def test_health_check_real(self, msf_config, msf_available):
        """Test health check against real service."""
        if not msf_available:
            pytest.skip("Metasploit RPC not available")
            
        source = MetasploitSource(
            password=msf_config["password"],
            host=msf_config["host"],
            port=msf_config["port"],
            ssl=True,
            timeout=30.0
        )
        
        try:
            is_healthy = await source.health_check()
            assert is_healthy is True
        except Exception as e:
            pytest.fail(f"Health check failed with error: {e}")

    @pytest.mark.asyncio
    async def test_query_real_module(self, msf_config, msf_available):
        """Test querying a known module."""
        if not msf_available:
            pytest.skip("Metasploit RPC not available")
            
        source = MetasploitSource(
            password=msf_config["password"],
            host=msf_config["host"],
            port=msf_config["port"],
            ssl=True,
            timeout=30.0
        )
        
        # Tomcat manager exploit is standard in MSF
        results = await source.query("tomcat", "manager")
        
        assert len(results) > 0
        found = False
        for r in results:
            if "tomcat_mgr_deploy" in r.metadata.get("module_path", ""):
                found = True
                assert r.exploit_available is True
                assert r.source == "metasploit"
                break
        
        assert found, "Expected tomcat_mgr_deploy module not found"

    @pytest.mark.asyncio
    async def test_query_no_results(self, msf_config, msf_available):
        """Test query with no matches."""
        if not msf_available:
            pytest.skip("Metasploit RPC not available")
            
        source = MetasploitSource(
            password=msf_config["password"],
            host=msf_config["host"],
            port=msf_config["port"],
            ssl=True,
            timeout=30.0
        )
        
        results = await source.query("nonexistent_service_xyz", "1.0.0")
        assert len(results) == 0
