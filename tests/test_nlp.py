import asyncio
import os
from src.core.council import CouncilOfExperts
from src.core.throttler import SwarmBrain

async def main():
    print("--- Testing NLP Intent Parser ---")
    brain = SwarmBrain(limit=5)
    council = CouncilOfExperts(brain, {})
    
    input_text = "Scan google.com for sql injection please"
    print(f"Input: {input_text}")
    
    result = await council.parse_intent(input_text)
    print(f"Result: {result}")
    
    if result.get("target") == "google.com" and "sql" in str(result.get("constraints") or result.get("action")).lower():
        print("✅ PASS")
    else:
        print("❌ FAIL")

if __name__ == "__main__":
    asyncio.run(main())
