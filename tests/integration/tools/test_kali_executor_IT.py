import pytest
from cyberred.tools.kali_executor import kali_execute, initialize_executor
from cyberred.tools.container_pool import ContainerPool, RealContainer
from cyberred.tools.scope import ScopeValidator, ScopeConfig

@pytest.mark.integration
@pytest.mark.asyncio
async def test_kali_execute_integration():
    # Setup Scope allowing all (for test)
    real_container_cls = RealContainer
    # Enable networking for apt-get
    original_network_mode = real_container_cls.NETWORK_MODE
    real_container_cls.NETWORK_MODE = "bridge"
    
    # Use from_config to handle string parsing
    scope_config_dict = {
        "allowed_targets": ["0.0.0.0/0"],  # Allow everything
        "allow_loopback": True,
        "allow_private": True
    }
    # Wrap in "scope" key as per from_config behavior (optional but good practice if mirroring yaml)
    scope = ScopeValidator.from_config(scope_config_dict)
    
    try:
        # Setup Pool
        async with ContainerPool(mode="real", size=1) as pool:
            # Prepare container: Install tools
            # We acquire directly to bypass ScopeValidator (apt-get has no target)
            print("Installing tools (nmap, iputils-ping)...")
            async with pool.acquire() as container:
                # Retry update
                for i in range(3):
                    res_up = await container.execute("apt-get update -o Acquire::Retries=5", timeout=120)
                    if res_up.success:
                        break
                    print(f"Apt update attempt {i+1} failed: {res_up.stderr}")
                    if i == 2:
                        # Don't assert here, try install anyway as some indices might be fetched
                        pass

                # Install with fix-missing
                res_inst = await container.execute("apt-get install -y --fix-missing nmap iputils-ping", timeout=600)
                if not res_inst.success:
                    print(f"Apt install failed: {res_inst.stderr}")
                    # Try one more time if failed
                    res_inst = await container.execute("apt-get install -y --fix-missing nmap iputils-ping", timeout=600)
                    if not res_inst.success:
                         # Last ditch: try installing just nmap
                         await container.execute("apt-get install -y nmap", timeout=300)
                         # We asserting later via execution check
                
                # Verify installation
                check_nmap = await container.execute("which nmap")
                if not check_nmap.success:
                     print("WARNING: nmap not found after install")
                     
            # Initialize Executor with Real Pool
            initialize_executor(pool=pool, scope_validator=scope)
            
            # Test 1: Ping 127.0.0.1
            # If ping failed to install, skip/warn but try nmap
            print("Running ping test...")
            result = await kali_execute("ping -c 1 127.0.0.1")
            
            # Test 2: Nmap 127.0.0.1 (Critical)
            print("Running nmap test...")
            result_nmap = await kali_execute("nmap -sn 127.0.0.1")
            if not result_nmap.success:
                print(f"Nmap failed: stdout='{result_nmap.stdout}', stderr='{result_nmap.stderr}'")
            assert result_nmap.success
            assert "Nmap scan report for" in result_nmap.stdout
            
    finally:
        # Restore permissions for other tests
        real_container_cls.NETWORK_MODE = original_network_mode
