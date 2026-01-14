"""Integration tests for ReconAgent.

These tests run against REAL Redis and REAL Kali containers.
They verify:
- AC8: ReconAgent performs real reconnaissance against cyber range targets
- Stigmergic signal propagation between agents
- End-to-end reconnaissance workflow with real tool execution

Requirements:
- Redis running on localhost:6379 (test-redis container)
- red-kali-worker image available
- Cyber range targets running (cyber-range-dvwa, cyber-range-ssh, etc.)
"""

import pytest
import uuid
import asyncio
import socket
from ipaddress import ip_network
from unittest.mock import patch, MagicMock, AsyncMock

from cyberred.agents.recon import ReconAgent
from cyberred.core.events import EventBus
from cyberred.core.models import Finding
from cyberred.tools.scope import ScopeValidator, ScopeConfig


def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture
def integration_scope_config():
    """Scope config that allows cyber-range targets and private IPs."""
    return ScopeConfig(
        allowed_networks=[
            ip_network("192.168.0.0/16"),
            ip_network("10.0.0.0/8"),
            ip_network("172.16.0.0/12"),
            ip_network("127.0.0.0/8"),  # Allow loopback for localhost targets
        ],
        allowed_hostnames=[
            "cyber-range-*",
            "localhost",
            "test.example.com",
        ],
        allowed_ports=[22, 80, 443, 8080, 2222, 445, 21, 139, 55553],
        allow_private=True,
        allow_loopback=True  # Allow loopback for local testing
    )


@pytest.fixture
def integration_scope_validator(integration_scope_config):
    """Pre-configured scope validator for integration tests."""
    return ScopeValidator(integration_scope_config)


@pytest.mark.integration
class TestReconAgentIntegration:
    """Integration tests for ReconAgent using REAL Redis."""

    @pytest.fixture
    async def event_bus(self):
        """Create EventBus connected to real Redis."""
        from cyberred.storage.redis_client import RedisClient
        from cyberred.core.config import RedisConfig
        
        # Verify Redis is available
        if not is_port_open("localhost", 6379):
            pytest.fail("Redis not available on localhost:6379 - start test-redis container")
        
        config = RedisConfig(host="localhost", port=6379)
        client = RedisClient(config, "int-eng")
        
        await client.connect()
        bus = EventBus(client)
        
        yield bus
        
        await client.close()

    @pytest.fixture
    def target(self):
        """Use localhost as target for real testing."""
        return "localhost"

    @pytest.mark.asyncio
    async def test_recon_workflow_real_redis(self, event_bus, target, integration_scope_validator):
        """Test full recon workflow with REAL Redis event bus."""
        with patch("cyberred.agents.recon.ReconAgent._get_scope_validator", 
                   return_value=integration_scope_validator):
            
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="int-eng-1",
                target=target,
                event_bus=event_bus
            )
            
            await agent.spawn()
            
            # Subscribe to findings on REAL Redis
            received_findings = []
            async def on_finding(channel, message):
                received_findings.append(message)
                
            await event_bus.subscribe("findings:*", on_finding)
            
            # Mock kali_execute to control tool output
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.stdout = "PORT   STATE SERVICE\n22/tcp open  ssh\n80/tcp open  http"
            mock_result.stderr = ""
            mock_result.exit_code = 0
            mock_result.error_type = None
            
            with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result
                
                findings, actions = await agent.execute_recon()
            
            # Assert NFR37: All actions have decision_context
            assert len(actions) == 5  # One action per tool
            for action in actions:
                assert action.decision_context, "NFR37: All actions must have decision_context"
            
            # Wait for Redis propagation
            await asyncio.sleep(0.3)
            
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_stigmergic_propagation_real_redis(self, event_bus, integration_scope_validator):
        """Test signal propagation via REAL Redis pub/sub."""
        with patch("cyberred.agents.recon.ReconAgent._get_scope_validator",
                   return_value=integration_scope_validator):
            
            agent1 = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-stigmergic",
                target="localhost",
                event_bus=event_bus
            )
            await agent1.spawn()
            
            # Publish strategy signal via REAL Redis
            channel = "strategies:eng-stigmergic"
            data = {"signal_id": "sig-real-test", "strategy": "stealth"}
            
            await event_bus.publish(channel, data)
            await asyncio.sleep(0.5)  # Allow real network propagation
            
            # Verify agent received it via decision context
            context = agent1.get_decision_context()
            assert "sig-real-test" in context
            
            # Verify strategy was updated
            assert agent1.current_strategy == "stealth"
            
            await agent1.shutdown()


@pytest.mark.integration
class TestReconAgentRealKali:
    """Integration tests using REAL Kali containers against cyber-range.
    
    These tests require:
    - Docker running with red-kali-worker image
    - Redis running on localhost:6379
    - Cyber-range targets running (DVWA, SSH, SMB, etc.)
    """
    
    @pytest.fixture
    async def event_bus(self):
        """Create EventBus connected to real Redis."""
        from cyberred.storage.redis_client import RedisClient
        from cyberred.core.config import RedisConfig
        
        if not is_port_open("localhost", 6379):
            pytest.fail("Redis not available on localhost:6379")
        
        config = RedisConfig(host="localhost", port=6379)
        client = RedisClient(config, "kali-eng")
        await client.connect()
        bus = EventBus(client)
        
        yield bus
        
        await client.close()

    @pytest.fixture
    def cyber_range_scope(self):
        """Scope config allowing cyber-range targets."""
        return ScopeConfig(
            allowed_networks=[
                ip_network("172.16.0.0/12"),  # Docker networks
                ip_network("127.0.0.0/8"),
                ip_network("10.0.0.0/8"),
            ],
            allowed_hostnames=[
                "localhost",
                "cyber-range-*",
            ],
            allowed_ports=[21, 22, 80, 139, 443, 445, 2222, 8080, 55553],
            allow_private=True,
            allow_loopback=True
        )

    @pytest.mark.asyncio
    async def test_real_recon_against_dvwa(self, event_bus, cyber_range_scope):
        """Test REAL reconnaissance against DVWA target (AC8).
        
        This runs actual nmap scans using the Kali container against DVWA.
        """
        # Verify DVWA is reachable
        if not is_port_open("localhost", 8080):
            pytest.fail("DVWA not available on localhost:8080 - start cyber-range")
        
        cyber_range_validator = ScopeValidator(cyber_range_scope)
        
        with patch("cyberred.agents.recon.ReconAgent._get_scope_validator",
                   return_value=cyber_range_validator):
            
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="dvwa-recon",
                target="localhost",
                event_bus=event_bus
            )
            
            await agent.spawn()
            
            # Use REAL kali_execute with real container pool
            from cyberred.tools.kali_executor import initialize_executor
            from cyberred.tools.container_pool import ContainerPool
            
            # Initialize with a real container pool (uses red-kali-worker by default)
            pool = ContainerPool(mode="real", size=1)
            try:
                await pool.initialize()
                initialize_executor(pool, cyber_range_validator)  # Not async
                
                # Execute real recon - this will run actual nmap, etc.
                findings, actions = await agent.execute_recon()
                
                # Verify actions were created with decision_context (NFR37)
                assert len(actions) > 0, "Should have created at least one action"
                for action in actions:
                    assert action.decision_context, "NFR37: All actions must have decision_context"
                    assert action.target == "localhost"
                
            finally:
                await pool.shutdown()
            
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_real_nmap_scan_ssh_target(self, event_bus, cyber_range_scope):
        """Test REAL nmap scan against SSH target on port 2222."""
        # Verify SSH target is reachable
        if not is_port_open("localhost", 2222):
            pytest.fail("SSH target not available on localhost:2222 - start cyber-range")
        
        cyber_range_validator = ScopeValidator(cyber_range_scope)
        
        with patch("cyberred.agents.recon.ReconAgent._get_scope_validator",
                   return_value=cyber_range_validator):
            
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="ssh-recon",
                target="localhost",
                event_bus=event_bus
            )
            
            await agent.spawn()
            
            # Generate the nmap command
            nmap_cmd = agent._generate_nmap_command("localhost")
            assert "nmap" in nmap_cmd
            assert "localhost" in nmap_cmd
            
            # Use REAL container pool to execute nmap
            from cyberred.tools.kali_executor import initialize_executor
            from cyberred.tools.container_pool import ContainerPool
            
            pool = ContainerPool(mode="real", size=1)
            try:
                await pool.initialize()
                initialize_executor(pool, cyber_range_validator)  # Not async
                
                # Execute real recon
                findings, actions = await agent.execute_recon()
                
                # Verify actions were created
                assert len(actions) > 0
                for action in actions:
                    assert action.decision_context
                    
            finally:
                await pool.shutdown()
            
            await agent.shutdown()

    @pytest.mark.asyncio
    async def test_real_container_pool_initialization(self):
        """Test that Kali container pool can be initialized with real containers."""
        from cyberred.tools.container_pool import ContainerPool
        import docker
        
        # Verify Docker is available and image exists
        try:
            client = docker.from_env()
            images = [img.tags for img in client.images.list() if img.tags]
            flat_tags = [tag for tags in images for tag in tags]
            
            if not any("red-kali-worker" in tag for tag in flat_tags):
                pytest.fail("red-kali-worker image not found - build it first")
        except Exception as e:
            pytest.fail(f"Docker not available: {e}")
        
        # Initialize real container pool (uses red-kali-worker by default)
        pool = ContainerPool(mode="real", size=1)
        
        try:
            await pool.initialize()
            
            # Verify pool has containers
            assert len(pool._all_containers) > 0, "Pool should have containers"
            
            # Acquire a container and run a command
            async with pool.acquire() as container:
                # Run simple command to verify container works
                result = await container.execute("echo 'kali-container-test'")
                assert result.exit_code == 0, f"Container execution failed: {result.stderr}"
                assert "kali-container-test" in result.stdout
                
        finally:
            await pool.shutdown()
