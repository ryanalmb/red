import asyncio
import logging
import json
from src.core.council import CouncilOfExperts
from src.core.worker_pool import WorkerPool
from src.mcp.nmap_adapter import NmapAdapter
from src.mcp.generic_adapter import GenericAdapter
from src.core.event_bus import EventBus

class GhostAgent:
    def __init__(self, agent_id: int, council: CouncilOfExperts, worker_pool: WorkerPool, event_bus: EventBus):
        self.id = agent_id
        self.council = council
        self.worker_pool = worker_pool
        self.bus = event_bus
        self.logger = logging.getLogger(f"Agent-{agent_id}")
        
        # Tools
        self.nmap = NmapAdapter(worker_pool)
        self.generic = GenericAdapter(worker_pool)

    async def engage(self, target: str):
        """
        The OODA Loop: Observe, Orient, Decide, Act.
        """
        # Sanitize Target (Remove http/https/trailing slash)
        clean_target = target.replace("http://", "").replace("https://", "").split("/")[0]
        
        await self._set_status("scanning")
        self.logger.info(f"Engaging {target} (Clean: {clean_target})")
        
        # 1. Observe (Quick Scan)
        scan_results = await self.nmap.scan_target(clean_target, ports="21,22,80,443,3000,8080")
        context = {"target": clean_target, "scan_results": scan_results}
        
        await self._log(f"Scan complete. Found {len(scan_results)} ports.")
        
        # 2. Orient & Decide (Council)
        await self._set_status("thinking")
        verdict = await self.council.decide_attack(context)
        
        if verdict["status"] == "VETOED":
            await self._log(f"CRITIC VETO: {verdict['reason']}", category="CRITIC")
            await self._set_status("idle")
            return

        command = verdict["command"]
        await self._log(f"Approved Strategy: {command}")

        # 3. Act (Execute)
        await self._set_status("attacking")
        
        # Dynamic Tool Selection (Simplified)
        # If command starts with 'nmap', use nmap adapter? No, generic is fine for raw commands.
        result = await self.generic.execute(command)
        
        # 4. Report
        await self._log(f"Execution Result: {result[:100]}...", category="SUCCESS")
        await self._set_status("idle")

    async def _set_status(self, status):
        # Update TUI
        await self.bus.publish("swarm:status", {"agent_id": self.id, "status": status})

    async def _log(self, message, category="INFO"):
        # Log to TUI
        await self.bus.publish("swarm:log", {
            "agent_id": self.id, 
            "category": category, 
            "message": message,
            "timestamp": "now" # In real app, generate timestamp
        })
