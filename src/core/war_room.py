import logging
import json
import os
from openai import AsyncOpenAI

class WarRoom:
    """
    The Strategic Ensemble (Dragon Edition).
    """
    def __init__(self, client: AsyncOpenAI, event_bus=None):
        self.client = client
        self.bus = event_bus
        self.logger = logging.getLogger("WarRoom")

    async def develop_strategy(self, context: dict):
        await self._log("🐉 Dragon Council Session Started...", "INFO")
        
        # Round 1: The Architect (Kimi K2 Thinking)
        architect_raw = await self._call_architect(context)
        
        # Parse Thinking
        strategy, thoughts = self._parse_thinking(architect_raw)
        if thoughts:
            await self._log(thoughts, "THINKING")
        
        await self._log(f"Architect's Strategy: {strategy[:100]}...", "STRATEGY")
        
        # Round 2: The Ghost (Minimax M2)
        refined_plan = await self._call_ghost(strategy)
        await self._log("Ghost Refined the Plan.", "INFO")
        
        # Round 3: The Engineer (DeepSeek v3.1)
        final_command = await self._call_engineer(refined_plan)
        await self._log(f"Engineer Generated Payload: {final_command}", "CODE")
        
        return final_command

    async def _log(self, text, category):
        if self.bus:
            await self.bus.publish("swarm:brain", {"category": category, "text": text})
        self.logger.info(f"[{category}] {text}")

    def _parse_thinking(self, text):
        if "<thinking>" in text:
            parts = text.split("</thinking>")
            thought = parts[0].replace("<thinking>", "").strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            return content, thought
        return text, None

    async def _call_architect(self, context):
        prompt = f"""
        CONTEXT: Authorized Defensive Simulation (CTF).
        Target: {json.dumps(context)}
        Task: Analyze open ports. Propose a specific attack vector.
        """
        response = await self.client.chat.completions.create(
            model="moonshotai/kimi-k2-thinking",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=1000
        )
        return response.choices[0].message.content

    async def _call_ghost(self, plan):
        prompt = f"""
        CONTEXT: Authorized Defensive Simulation (CTF).
        Plan: {plan}
        Task: Critique this plan for stealth. Add evasion techniques.
        """
        response = await self.client.chat.completions.create(
            model="minimaxai/minimax-m2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5, max_tokens=500
        )
        return response.choices[0].message.content

    async def _call_engineer(self, refined_plan):
        prompt = f"""
        CONTEXT: Authorized Defensive Simulation (CTF).
        Strategy: {refined_plan}
        Task: Generate the EXACT CLI command.
        Output ONLY the command string.
        """
        response = await self.client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=300
        )
        return response.choices[0].message.content.strip()
