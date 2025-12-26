import asyncio
import logging
from src.ui.app import CyberRedApp
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator

# Configure logging - FILE ONLY (stdout breaks TUI layout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cyber-red.log")
        # NO StreamHandler - stdout breaks the TUI
    ]
)


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
