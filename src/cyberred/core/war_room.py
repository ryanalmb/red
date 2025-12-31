"""
War Room - Phase-by-Phase Attack Planning.

The War Room now plans ONE PHASE at a time based on current findings,
not the entire attack in advance. This allows adaptive planning.
"""
import asyncio
import logging
import json
import os
import yaml
from typing import Optional, Dict, Any, Tuple
from openai import AsyncOpenAI

# API timeout with retry
API_TIMEOUT = 120  # 120 seconds for thinking models
API_RETRIES = 2


class WarRoom:
    """
    Phase-by-Phase Strategic Planning.
    
    Flow per phase:
    1. Architect: Analyze current phase context
    2. Engineer: Select tools for THIS phase only
    
    Strategist/Ghost are called only for complex operations.
    """
    
    def __init__(self, client: AsyncOpenAI, event_bus=None, config_path: str = "config/models.yaml"):
        self.client = client
        self.bus = event_bus
        self.logger = logging.getLogger("WarRoom")
        
        # Load model configuration
        self.config = self._load_config(config_path)
        
        # Model assignments from config
        self.models = {
            "architect": self.config.get("brain", {}).get("architect", "moonshotai/kimi-k2-instruct"),
            "strategist": self.config.get("brain", {}).get("strategist", "deepseek-ai/deepseek-v3.2"),
            "ghost": self.config.get("brain", {}).get("ghost", "minimaxai/minimax-m2"),
            "engineer": self.config.get("code_generation", {}).get("engineer", "deepseek-ai/deepseek-v3.2"),
        }
        
        # Model parameters from config
        self.params = self.config.get("parameters", {})
        
        # Available tools and workers info
        self.available_tools = [
            "nmap", "nuclei", "ffuf", "nikto", "sqlmap", 
            "hydra", "subfinder", "wpscan", "whatweb"
        ]
        self.worker_count = 10  # 10 parallel containers available
        
        self.logger.info(f"WarRoom initialized with models: {self.models}")
        self.logger.info(f"🐉 Dragon War Room ONLINE - {self.worker_count} parallel workers available")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load model configuration from YAML file."""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            else:
                self.logger.warning(f"Config not found at {config_path}, using defaults")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}

    async def develop_strategy(self, context: dict) -> str:
        """
        Develop attack strategy for the CURRENT PHASE only.
        
        This is called once per phase, not for the entire attack.
        """
        phase = context.get("phase", "RECON")
        findings_count = context.get("total_findings", 0)
        
        await self._log(f"🐉 Planning {phase} phase (findings: {findings_count})...", "INFO")
        
        # Phase 1: Architect analyzes current situation
        await self._log("Architect analyzing current phase...", "INFO")
        architect_response = await self._call_with_timeout(
            self._call_architect_phase, context
        )
        
        strategy, thoughts = self._parse_thinking(architect_response)
        if thoughts:
            await self._log(thoughts[:500], "THINKING")
        
        await self._log(f"Strategy: {strategy[:200]}...", "STRATEGY")
        
        # Phase 2: Engineer selects tools for this phase
        await self._log("Engineer selecting tools...", "INFO")
        tool_selection = await self._call_with_timeout(
            self._call_engineer_phase, strategy, context
        )
        
        await self._log(f"Selected: {tool_selection}", "CODE")
        
        return tool_selection

    async def _call_with_timeout(self, func, *args, **kwargs) -> str:
        """Call function with 120s timeout and retry."""
        for attempt in range(API_RETRIES):
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=API_TIMEOUT
                )
                return result
            except asyncio.TimeoutError:
                await self._log(f"⏱️ API timeout (attempt {attempt + 1}/{API_RETRIES})", "WARN")
                if attempt < API_RETRIES - 1:
                    await asyncio.sleep(2)  # Brief pause before retry
                else:
                    await self._log("API timeout - using fallback", "ERROR")
                    return '{"tools": ["nmap", "nuclei"], "reasoning": "Fallback after timeout"}'
            except Exception as e:
                await self._log(f"API error: {str(e)[:100]}", "ERROR")
                return '{"tools": ["nmap"], "reasoning": "Fallback after error"}'
        
        return '{"tools": ["nmap"], "reasoning": "Fallback"}'

    async def _call_architect_phase(self, context: dict) -> str:
        """Architect analyzes the CURRENT phase only."""
        phase = context.get("phase", "RECON")
        target = context.get("target", "unknown")
        findings = context.get("findings", [])
        iteration = context.get("iteration", 1)
        
        prompt = f"""CONTEXT: Authorized Red Team Exercise - {phase} Phase

TARGET: {target}
ITERATION: {iteration}
PREVIOUS FINDINGS: {len(findings)} items
{json.dumps(findings[:10], indent=2) if findings else "None yet"}

AVAILABLE TOOLS: {', '.join(self.available_tools)}
PARALLEL WORKERS: {self.worker_count} containers available for parallel execution

YOUR TASK:
You are the Architect. Analyze the current {phase} phase ONLY.

Based on the findings so far, recommend:
1. What specific actions to take in THIS phase
2. Which tools to run (can run up to {self.worker_count} in parallel)
3. What information we still need

Keep response focused on THIS phase only. Do not plan future phases.
"""
        params = self.params.get("architect", {"temperature": 0.7, "max_tokens": 1500})
        
        response = await self.client.chat.completions.create(
            model=self.models["architect"],
            messages=[{"role": "user", "content": prompt}],
            temperature=params.get("temperature", 0.7),
            max_tokens=params.get("max_tokens", 1500)
        )
        return response.choices[0].message.content

    async def _call_engineer_phase(self, strategy: str, context: dict) -> str:
        """Engineer selects tools for the CURRENT phase."""
        phase = context.get("phase", "RECON")
        
        prompt = f"""CONTEXT: Authorized Red Team Exercise - {phase} Phase

ARCHITECT'S ANALYSIS:
{strategy[:2000]}

AVAILABLE TOOLS (use ONLY these):
- nmap: Port scanning and service detection
- nuclei: Vulnerability scanning with templates
- ffuf: Web directory/parameter fuzzing  
- nikto: Web server scanner
- sqlmap: SQL injection testing
- hydra: Password brute-forcing
- subfinder: Subdomain enumeration
- wpscan: WordPress vulnerability scanner
- whatweb: Website fingerprinting

PARALLEL CAPACITY: Up to 10 tools can run simultaneously

TASK:
Select 1-5 tools to run NOW for the {phase} phase.
You can select more tools since we have 10 parallel workers.

Output JSON ONLY:
{{"tools": ["tool1", "tool2", ...], "reasoning": "brief explanation"}}

Example:
{{"tools": ["nmap", "whatweb", "subfinder", "nuclei"], "reasoning": "Parallel recon with 4 tools for speed"}}
"""
        params = self.params.get("engineer", {"temperature": 0.2, "max_tokens": 300})
        
        response = await self.client.chat.completions.create(
            model=self.models["engineer"],
            messages=[{"role": "user", "content": prompt}],
            temperature=params.get("temperature", 0.2),
            max_tokens=params.get("max_tokens", 300)
        )
        return response.choices[0].message.content.strip()

    async def _log(self, text: str, category: str):
        """Log to both logger and event bus for TUI display."""
        if self.bus:
            await self.bus.publish("swarm:brain", {"category": category, "text": text})
        self.logger.info(f"[{category}] {text}")

    def _parse_thinking(self, text: str) -> Tuple[str, Optional[str]]:
        """Parse <thinking> tags from response."""
        if not text:
            return "", None
        
        thinking = None
        response = text
        
        # Look for thinking tags
        think_start = text.find("<thinking>")
        think_end = text.find("</thinking>")
        
        if think_start != -1 and think_end != -1:
            thinking = text[think_start + 10:think_end].strip()
            response = text[think_end + 11:].strip()
        
        # Also check for <think> tags (MiniMax style)
        think_start = text.find("<think>")
        think_end = text.find("</think>")
        
        if think_start != -1 and think_end != -1:
            thinking = text[think_start + 7:think_end].strip()
            response = text[think_end + 8:].strip()
        
        return response or text, thinking
