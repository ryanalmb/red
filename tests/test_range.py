import pytest
from testcontainers.core.container import DockerContainer
import asyncio

@pytest.mark.asyncio
@pytest.mark.integration
async def test_cyber_range_connectivity():
    """
    Verify cyber-range targets are reachable.
    Uses ephemeral Kali container and bash /dev/tcp checks (dependency-free).
    """
    network_name = "cyber-range-net"
    
    # Target container names (from docker-compose.yml)
    targets = {
        "web": ("cyber-range-dvwa", 80),
        "ssh": ("cyber-range-ssh", 2222),
        "smb": ("cyber-range-smb", 445),
        "ftp": ("cyber-range-ftp", 21)
    }

    # Start ephemeral attacker container
    with DockerContainer("kalilinux/kali-rolling") \
        .with_kwargs(network=network_name) \
        .with_command("tail -f /dev/null") as kali:
        
        # Helper to check port
        def check_port(host, port):
            # Use bash built-in /dev/tcp
            cmd = f"bash -c 'timeout 1 cat < /dev/tcp/{host}/{port}'" 
            # Note: cat < /dev/tcp opens connection. If successful, exit 0. timeout ensures we don't hang on read.
            # Alternately: timeout 1 bash -c 'echo > /dev/tcp/...'
            cmd = f"timeout 2 bash -c 'echo > /dev/tcp/{host}/{port}'"
            res = kali.exec(cmd)
            return res.exit_code == 0, res.output.decode()

        # 1. Verify DVWA (Web)
        host, port = targets["web"]
        print(f"Testing {host}:{port}...")
        success, out = check_port(host, port)
        assert success, f"Failed to connect to {host}:{port}. Output: {out}"
        
        # 2. Verify SSH
        host, port = targets["ssh"]
        print(f"Testing {host}:{port}...")
        success, out = check_port(host, port)
        assert success, f"Failed to connect to {host}:{port}. Output: {out}"
        
        # 3. Verify SMB
        host, port = targets["smb"]
        print(f"Testing {host}:{port}...")
        success, out = check_port(host, port)
        assert success, f"Failed to connect to {host}:{port}. Output: {out}"

        # 4. Verify FTP
        host, port = targets["ftp"]
        print(f"Testing {host}:{port}...")
        success, out = check_port(host, port)
        assert success, f"Failed to connect to {host}:{port}. Output: {out}"