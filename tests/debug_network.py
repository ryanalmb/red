import asyncio
from src.core.worker_pool import WorkerPool

async def main():
    pool = WorkerPool(pool_size=1, container_prefix="red-kali-worker")
    print("--- Debugging Network ---")
    
    # Ping Metasploitable
    print("Pinging metasploitable...")
    res = await pool.execute_task("ping -c 3 red-metasploitable-1", "ping")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
