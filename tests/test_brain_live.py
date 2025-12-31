import asyncio
import os
from cyberred.core.council import CouncilOfExperts
from cyberred.core.throttler import SwarmBrain

# Mock RoE for test
MOCK_ROE = {
    "allowed_ips": ["192.168.1.5"],
    "forbidden_ports": [21],
    "aggression": "HIGH"
}

async def main():
    print("--- Testing Live Brain (NVIDIA NIM) ---")
    
    # Init Components
    brain = SwarmBrain(limit=5)
    council = CouncilOfExperts(brain, MOCK_ROE)
    
    # Mock Context
    context = {"ip": "192.168.1.5", "port": 80, "service": "Apache 2.4.49"}
    
    print(f"Input Context: {context}")
    print("Thinking... (This calls Llama 3.1 405B -> Codestral -> Llama 3 70B)")
    
    try:
        result = await council.decide_attack(context)
        print("\n--- Council Verdict ---")
        print(result)
        
        if result["status"] in ["APPROVED", "VETOED"]:
            print("✅ PASS: Brain cycle completed.")
        else:
            print("❌ FAIL: Unexpected status.")
            
    except Exception as e:
        print(f"❌ FAIL: {e}")

if __name__ == "__main__":
    asyncio.run(main())
