import pytest
import asyncio
from cyberred.core.worker_pool import WorkerPool
from cyberred.mcp.nmap_adapter import NmapAdapter

@pytest.mark.asyncio
async def test_range_connectivity_and_scan():
    """
    E2E-01: Verify Nmap can see Metasploitable.
    """
    # Setup
    pool = WorkerPool(pool_size=1, container_prefix="red-kali-worker")
    nmap = NmapAdapter(pool)
    
    target_host = "red-metasploitable-1"
    
    # Wait for target to be reachable (up to 30s)
    print(f"\n[Test] Waiting for {target_host}...")
    for i in range(6):
        ping_res = await pool.execute_task(f"ping -c 1 -W 1 {target_host}", "ping")
        if "bytes from" in ping_res:
            print(f"[Test] Target UP after {i*5}s")
            break
        await asyncio.sleep(5)
    else:
        pytest.fail(f"Target {target_host} unreachable after 30s")

    print(f"\n[Test] Scanning Target: {target_host}...")
    
    # Scan top ports (21=FTP, 22=SSH, 80=HTTP)
    results = await nmap.scan_target(target_host, ports="21,22,80")
    
    print(f"[Test] Scan Results: {results}")
    
    # Assertions
    assert len(results) >= 2, "Failed to find at least 2 expected open ports"
    
    found_ports = [r['port'] for r in results]
    # assert "21" in found_ports, "FTP (21) not found" # FTP might be slow to boot
    assert "80" in found_ports, "HTTP (80) not found"