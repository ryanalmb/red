import asyncio
import logging
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.core.council import CouncilOfExperts
from src.core.throttler import SwarmBrain
from src.core.roe_loader import RoELoader

# Configure Logging to Console
logging.basicConfig(level=logging.INFO)

async def main():
    print("--- STRICT E2E DEBUG START ---")
    
    # 1. Setup Infra
    bus = EventBus()
    
    # 2. Start Orchestrator
    orch = Orchestrator(bus)
    await orch.start()
    print("✅ Orchestrator Started")

    # 3. Simulate User Input Parsing (Mocking the Brain for speed, or use real if needed)
    # We want to test the EXACT failure case: A URL.
    user_input = "Scan scanme.nmap.org"
    print(f"User Input: {user_input}")
    
    # Manually Parse
    intent = {
        "target": "scanme.nmap.org",
        "action": "scan",
        "scope": "network"
    }
    print(f"Parsed Intent: {intent}")
    
    # 4. Publish Job (Simulating TUI)
    print("🚀 Publishing Job to Redis...")
    await bus.publish("job:new", intent)
    
    # 5. Listen for Agent Logs (to see if it wakes up)
    print("👂 Listening for Agent Logs...")
    
    async def log_listener():
        ps = bus.redis.pubsub()
        await ps.subscribe("swarm:log", "swarm:status")
        async for message in ps.listen():
            if message["type"] == "message":
                import json
                data = json.loads(message["data"])
                print(f"🔔 EVENT: {data}")
                if "scan complete" in str(data).lower():
                    print("✅ Agent finished scanning")
                if "nmap failed" in str(data).lower():
                    print("❌ Agent reported Nmap failure")

    # Run listener for 20 seconds
    try:
        await asyncio.wait_for(log_listener(), timeout=20)
    except asyncio.TimeoutError:
        print("⚠️ Test Timed Out (Agent never reported back)")

    await bus.close()

if __name__ == "__main__":
    asyncio.run(main())
