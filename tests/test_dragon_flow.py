import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from cyberred.core.orchestrator import Orchestrator
from cyberred.core.event_bus import EventBus

# Valid XML for Nmap Adapter
MOCK_XML = """<?xml version="1.0"?>
<nmaprun>
<host><status state="up"/>
<ports>
<port protocol="tcp" portid="80"><state state="open" reason="syn-ack"/><service name="http"/></port>
</ports>
</host>
</nmaprun>
"""

@pytest.mark.asyncio
async def test_dragon_flow_logic():
    # 1. Setup Infra
    bus = EventBus()
    orch = Orchestrator(bus)
    
    # 2. Mock Internal Components
    # We patch the components instance on the Orchestrator
    
    # Mock Council's WarRoom methods
    orch.council.war_room._call_architect = AsyncMock(return_value="Strategy: Attack Port 80")
    orch.council.war_room._call_ghost = AsyncMock(return_value="Strategy: Attack Port 80 (Stealth)")
    orch.council.war_room._call_engineer = AsyncMock(return_value="nmap -p 80 target")
    
    # Mock Council Intent Parser
    orch.council.parse_intent = AsyncMock(return_value={
        "target": "127.0.0.1", "action": "scan", "scope": "network"
    })
    
    # Mock WorkerPool to return XML
    orch.pool.execute_task = AsyncMock(return_value=MOCK_XML)
    
    # 3. Start
    await orch.start()
    
    # 4. Trigger
    print("Injecting Command...")
    await bus.publish("cmd:nlp", {"text": "Scan localhost"})
    
    # 5. Wait for Result
    future = asyncio.get_running_loop().create_future()
    
    async def verifier(data):
        print(f"DEBUG EVENT: {data}")
        # Check for the specific log from WarRoom
        if "Engineer Generated Payload" in data.get("text", ""):
            if not future.done():
                future.set_result(True)
                
    await bus.subscribe("swarm:brain", verifier)
    
    try:
        await asyncio.wait_for(future, timeout=5.0)
        print("✅ War Room Cycle Verified")
    except asyncio.TimeoutError:
        pytest.fail("Timeout waiting for War Room")
        
    await bus.close()