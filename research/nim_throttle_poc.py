import asyncio
import time
import random

# Simulation of NVIDIA NIM Client
class MockNIMClient:
    async def chat_completion(self, prompt):
        # Simulate network latency (0.5s to 2.0s)
        await asyncio.sleep(random.uniform(0.5, 2.0))
        return "Analysis Complete"

# The Token Bucket Throttler
class SwarmBrain:
    def __init__(self, limit=30): # Lowered to 30 RPM based on research
        self.limit = limit
        self.semaphore = asyncio.Semaphore(limit)
        self.client = MockNIMClient()
        self.request_count = 0

    async def think(self, agent_id, prompt):
        async with self.semaphore:
            # print(f"[Agent-{agent_id}] Thinking...")
            start = time.time()
            response = await self.client.chat_completion(prompt)
            duration = time.time() - start
            return duration

async def main():
    brain = SwarmBrain(limit=10) # Set low limit for demo purposes
    
    print("--- Starting Swarm (50 Agents, Limit 10) ---")
    start_time = time.time()
    
    tasks = []
    for i in range(50):
        tasks.append(brain.think(i, "Attack Plan"))
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    print(f"--- Swarm Complete ---")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Total Requests: {len(results)}")
    print(f"Note: If synchronous, time would be ~50s. With Async+Limit(10), it took {total_time:.2f}s.")

if __name__ == "__main__":
    asyncio.run(main())
