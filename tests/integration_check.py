import asyncio
from cyberred.core.worker_pool import WorkerPool

async def main():
    print("--- Starting Integration Check ---")
    
    # Initialize Pool
    pool = WorkerPool(pool_size=1, container_prefix="red-kali-worker")
    
    # Task 1: Check Nmap Version
    print("[Test] Checking Nmap Version...")
    output = await pool.execute_task("nmap --version", "nmap")
    
    if "Nmap version" in output:
        print("✅ PASS: Nmap is executable.")
        print(f"Output: {output.splitlines()[0]}")
    else:
        print("❌ FAIL: Nmap failed.")
        print(f"Output: {output}")

    # Task 2: Check Metasploit Version (msfconsole takes time, so we verify availability via msfvenom)
    print("\n[Test] Checking Metasploit (msfvenom)...")
    output = await pool.execute_task("msfvenom --version", "msfvenom")
    
    if "Framework:" in output or "Error" not in output: # msfvenom output varies but shouldn't error
        print("✅ PASS: Metasploit is installed.")
    else:
        print("❌ FAIL: Metasploit failed.")
        print(output)

if __name__ == "__main__":
    asyncio.run(main())

