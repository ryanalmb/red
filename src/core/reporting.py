import json
import datetime
import os
import logging
from src.core.event_bus import EventBus

class ReportGenerator:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.logger = logging.getLogger("ReportGenerator")

    async def generate_markdown(self, output_dir="reports"):
        """
        Generates a markdown report from the current Hive State.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(output_dir, f"CyberRed-Report-{timestamp}.md")
        os.makedirs(output_dir, exist_ok=True)

        # Fetch Data from Redis
        # Note: In a real app, we'd query specific keys. 
        # For MVP, we assume keys are known or we scan 'target:*'
        
        # Simulating data fetching for now as we don't have a 'get_all_targets' method in EventBus
        # In a real implementation, EventBus/Redis wrapper should expose query methods.
        # We will iterate keys using the redis client directly.
        
        try:
            keys = await self.bus.redis.keys("target:*")
            targets = []
            for key in keys:
                # Assuming key format target:{ip}:info or target:{ip}:ports
                # Simplification: We grab everything
                val = await self.bus.redis.get(key)
                targets.append(f"- **{key}**: {val}")
            
            content = f"""# Cyber-Red Engagement Report
**Date:** {datetime.datetime.now()}
**Status:** Generated

## 1. Executive Summary
Automatic assessment performed by Cyber-Red Swarm.
Total Targets Found: {len(targets)}

## 2. Attack Surface
{chr(10).join(targets) if targets else "No targets found in Hive Memory."}

## 3. Vulnerabilities
*(Vulnerability data would be queried from 'vuln:*' keys here)*

## 4. Remediation
Recommended actions based on findings.
"""
            with open(filename, "w") as f:
                f.write(content)
            
            self.logger.info(f"Report generated: {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Reporting failed: {e}")
            return None
