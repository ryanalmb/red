import asyncio
from src.ui.app import CyberRedApp
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator

async def run_app():
    # 1. Initialize Bus
    bus = EventBus()
    
    # 2. Initialize Orchestrator (The Hive Mind)
    orch = Orchestrator(bus)
    await orch.start()

    # 3. Initialize App (The Face)
    app = CyberRedApp(event_bus=bus)
    
    # 4. Run App (Blocking)
    await app.run_async()
    
    # 5. Cleanup
    await bus.close()

def main():
    asyncio.run(run_app())

if __name__ == "__main__":
    main()
