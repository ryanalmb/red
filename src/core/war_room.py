import logging
import json
import os
import yaml
from typing import Optional, Dict, Any, Tuple
from openai import AsyncOpenAI


class WarRoom:
    """
    The Strategic Ensemble (Dragon Edition).
    
    Uses a Council of AI models for attack strategy development:
    - Architect (Kimi K2 Thinking): Initial strategy with chain-of-thought
    - Strategist (DeepSeek v3.2): Deep analysis and planning
    - Ghost (MiniMax M2): Evasion and stealth optimization
    - Engineer (DeepSeek v3.2): Payload/command generation
    """
    
    def __init__(self, client: AsyncOpenAI, event_bus=None, config_path: str = "config/models.yaml"):
        self.client = client
        self.bus = event_bus
        self.logger = logging.getLogger("WarRoom")
        
        # Load model configuration
        self.config = self._load_config(config_path)
        
        # Model assignments from config
        self.models = {
            "architect": self.config.get("brain", {}).get("architect", "moonshotai/kimi-k2-thinking"),
            "strategist": self.config.get("brain", {}).get("strategist", "deepseek-ai/deepseek-v3.2"),
            "ghost": self.config.get("brain", {}).get("ghost", "minimaxai/minimax-m2"),
            "engineer": self.config.get("code_generation", {}).get("engineer", "deepseek-ai/deepseek-v3.2"),
        }
        
        # Model parameters from config
        self.params = self.config.get("parameters", {})
        
        self.logger.info(f"WarRoom initialized with models: {self.models}")
        self.logger.info(f"🐉 Dragon War Room ONLINE - Kimi K2 / DeepSeek v3.2 / MiniMax M2")


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
        Develop attack strategy using the full War Room ensemble.
        
        Flow: Architect → Strategist → Ghost → Engineer
        """
        await self._log("🐉 Dragon Council Session Started...", "INFO")
        
        # Round 1: The Architect (Kimi K2 Thinking - Chain of Thought)
        await self._log("Phase 1: Architect analyzing attack surface...", "INFO")
        architect_raw = await self._call_architect(context)
        
        # Parse Thinking tags
        strategy, thoughts = self._parse_thinking(architect_raw)
        if thoughts:
            await self._log(thoughts, "THINKING")
        
        await self._log(f"Architect's Strategy: {strategy[:200]}...", "STRATEGY")
        
        # Round 2: The Strategist (DeepSeek v3.2 - Deep Analysis)
        await self._log("Phase 2: Strategist refining approach...", "INFO")
        refined_plan = await self._call_strategist(context, strategy)
        await self._log(f"Strategist's Refinement: {refined_plan[:200]}...", "STRATEGY")
        
        # Round 3: The Ghost (MiniMax M2 - Evasion)
        await self._log("Phase 3: Ghost adding evasion techniques...", "INFO")
        stealthy_plan = await self._call_ghost(refined_plan)
        await self._log("Ghost added evasion layer.", "INFO")
        
        # Round 4: The Engineer (DeepSeek v3.2 - Command Generation)
        await self._log("Phase 4: Engineer generating payload...", "INFO")
        final_command = await self._call_engineer(stealthy_plan)
        await self._log(f"Engineer Generated: {final_command}", "CODE")
        
        return final_command

    async def _log(self, text: str, category: str):
        """Log to both logger and event bus for TUI display."""
        if self.bus:
            await self.bus.publish("swarm:brain", {"category": category, "text": text})
        self.logger.info(f"[{category}] {text}")

    def _parse_thinking(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Parse Kimi K2's <thinking> tags to separate reasoning from response.
        
        Returns: (response_content, thinking_content or None)
        """
        if "<thinking>" in text:
            parts = text.split("</thinking>")
            thought = parts[0].replace("<thinking>", "").strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            return content, thought
        return text, None

    async def _call_architect(self, context: dict) -> str:
        """
        Use Kimi K2 Thinking for initial strategic planning.
        
        This model excels at chain-of-thought reasoning with visible <thinking> tags.
        """
        prompt = f"""
CONTEXT: Authorized Defensive Simulation (CTF/Red Team Exercise).
You are the Architect - the strategic mastermind of the attack.

TARGET CONTEXT:
{json.dumps(context, indent=2)}

INSTRUCTIONS:
Use <thinking> tags to reason through your analysis before providing your strategy.

Consider:
1. What attack vectors are available based on the open ports/services?
2. What is the optimal attack sequence?
3. What tools would be most effective?
4. Are there any quick wins (default credentials, known CVEs)?

Provide:
1. Primary attack path with specific steps
2. Secondary/fallback strategies
3. Recommended tools in order of priority
4. Estimated success probability

Output your detailed attack strategy.
"""
        params = self.params.get("architect", {"temperature": 0.7, "max_tokens": 2000})
        
        try:
            await self._log(f"Calling {self.models['architect']}...", "API")
            response = await self.client.chat.completions.create(
                model=self.models["architect"],
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 2000)
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = f"Architect API failed: {str(e)}"
            self.logger.error(error_msg)
            await self._log(f"❌ {error_msg}", "ERROR")
            # Try fallback model
            return await self._call_with_fallback("architect", prompt, params)


    async def _call_strategist(self, context: dict, architect_plan: str) -> str:
        """
        Use DeepSeek v3.2 for deep strategic analysis and refinement.
        
        This model has 685B parameters with sparse attention for complex reasoning.
        """
        prompt = f"""
CONTEXT: Authorized Defensive Simulation (CTF/Red Team Exercise).
You are the Strategist - the tactical planner who refines attack approaches.

ORIGINAL CONTEXT:
{json.dumps(context, indent=2)}

ARCHITECT'S INITIAL PLAN:
{architect_plan}

INSTRUCTIONS:
Analyze and refine the Architect's plan. Consider:

1. Tool Ordering: What is the optimal sequence of tools to minimize detection?
2. Parallelization: Which scans/attacks can run simultaneously?
3. Result Correlation: How should findings from one tool inform the next?
4. Resource Efficiency: How to maximize coverage with minimum noise?
5. Fallback Chains: If primary attack fails, what's the backup sequence?

Provide a refined, actionable attack plan with specific tool commands.
"""
        params = self.params.get("strategist", {"temperature": 0.5, "max_tokens": 1500})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.models["strategist"],
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.5),
                max_tokens=params.get("max_tokens", 1500)
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Strategist call failed: {e}")
            return architect_plan  # Return original if refinement fails

    async def _call_ghost(self, plan: str) -> str:
        """
        Use MiniMax M2 for evasion and stealth optimization.
        
        This 230B MoE model is optimized for tool-use and agent workflows.
        """
        prompt = f"""
CONTEXT: Authorized Defensive Simulation (CTF/Red Team Exercise).
You are the Ghost - the evasion specialist.

CURRENT PLAN:
{plan}

INSTRUCTIONS:
Review this attack plan and add evasion techniques. Consider:

1. Detection Avoidance: How to avoid IDS/IPS triggers?
2. Timing: Should attacks be staggered to avoid correlation?
3. Traffic Obfuscation: Proxy chains, traffic padding, protocol manipulation?
4. Log Evasion: Techniques to minimize forensic footprint?
5. Credential Handling: How to safely exfiltrate or use found credentials?

Modify the plan to maximize stealth while maintaining effectiveness.
Output the enhanced plan with evasion measures integrated.
"""
        params = self.params.get("ghost", {"temperature": 0.5, "max_tokens": 500})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.models["ghost"],
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.5),
                max_tokens=params.get("max_tokens", 500)
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Ghost call failed: {e}")
            return plan  # Return original if evasion layer fails

    async def _call_engineer(self, refined_plan: str) -> str:
        """
        Use DeepSeek v3.2 for precise command/payload generation.
        
        Low temperature for deterministic, syntactically correct output.
        """
        prompt = f"""
CONTEXT: Authorized Defensive Simulation (CTF/Red Team Exercise).
You are the Engineer - the payload specialist.

REFINED STRATEGY:
{refined_plan}

INSTRUCTIONS:
Generate the EXACT CLI command(s) to execute the first step of this attack.

Requirements:
1. Output ONLY the command string(s) - no explanations
2. Commands must be syntactically correct
3. Include all necessary flags and options
4. If multiple commands needed, separate with semicolons
5. Use full paths where appropriate

Example outputs:
- nmap -sV -sC -p- 192.168.1.1
- sqlmap -u "http://target.com/page?id=1" --batch --dbs
- nuclei -u http://target.com -severity critical,high -json

Output the command(s) now:
"""
        params = self.params.get("engineer", {"temperature": 0.2, "max_tokens": 1000})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.models["engineer"],
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.2),
                max_tokens=params.get("max_tokens", 1000)
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Engineer call failed: {e}")
            # Return a safe default scan command
            return "nmap -sV -sC -T4 --top-ports 1000"

    async def _call_with_fallback(self, role: str, prompt: str, params: dict) -> str:
        """Try fallback model if primary fails."""
        fallback_models = self.config.get("fallback", {})
        fallback_model = fallback_models.get(role)
        
        if not fallback_model:
            return "ERROR: Primary model failed and no fallback configured"
        
        self.logger.info(f"Trying fallback model for {role}: {fallback_model}")
        
        try:
            response = await self.client.chat.completions.create(
                model=fallback_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.5),
                max_tokens=params.get("max_tokens", 1000)
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Fallback also failed: {e}")
            return f"ERROR: Both primary and fallback models failed: {e}"

    async def quick_command(self, context: dict) -> str:
        """
        Fast path: Skip full council, use Engineer directly for simple tasks.
        
        Use when you already know what needs to be done.
        """
        prompt = f"""
CONTEXT: Authorized Defensive Simulation.
TARGET: {json.dumps(context)}

Generate the appropriate CLI command for this target.
Output ONLY the command string.
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.models["engineer"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Quick command failed: {e}")
            return f"ERROR: {e}"
