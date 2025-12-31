"""
Ghost Agent - AI-Directed Attack Agent.

The Ghost Agent executes attacks driven by the War Room AI ensemble.
The War Room develops strategy FIRST, then the agent executes.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List

from cyberred.core.council import CouncilOfExperts
from cyberred.core.tool_orchestrator import ToolOrchestrator
from cyberred.core.event_bus import EventBus


class GhostAgent:
    """
    AI-Directed Attack Agent.
    
    Flow:
    1. War Room develops initial strategy
    2. Agent executes recommended tools
    3. War Room analyzes results and plans next move
    4. Repeat until objective achieved
    """
    
    def __init__(self, agent_id: int, council: CouncilOfExperts, 
                 tool_orchestrator: ToolOrchestrator, event_bus: EventBus):
        self.id = agent_id
        self.council = council
        self.orchestrator = tool_orchestrator
        self.bus = event_bus
        self.logger = logging.getLogger(f"Agent-{agent_id}")
        
        # Attack state
        self.target: Optional[str] = None
        self.is_active = False
        self.context: Dict[str, Any] = {}
        self.findings: List[Dict[str, Any]] = []
        self.phase = "INIT"
    
    async def engage(self, target: str, max_iterations: int = 10):
        """
        AI-directed attack loop.
        
        The War Room is consulted FIRST before any tools run.
        """
        self.target = self._sanitize_target(target)
        self.is_active = True
        self.context = {"target": self.target, "phase": "RECON", "findings": []}
        
        self.logger.info(f"Engaging target: {self.target}")
        await self._set_status("initializing")
        await self._log(f"🎯 Target acquired: {self.target}", "INFO")
        
        iteration = 0
        
        try:
            while self.is_active and iteration < max_iterations:
                iteration += 1
                await self._log(f"━━━ Iteration {iteration} ━━━", "PHASE")
                
                # ═══════════════════════════════════════════════════
                # STEP 1: CONSULT WAR ROOM (AI-first approach)
                # ═══════════════════════════════════════════════════
                await self._set_status("thinking")
                await self._log("🐉 Consulting War Room for strategy...", "INFO")
                
                strategy = await self.council.decide_attack(self.context)
                
                if strategy["status"] == "VETOED":
                    await self._log(f"⛔ VETOED: {strategy['reason']}", "CRITIC")
                    break
                
                if strategy["status"] == "COMPLETE":
                    await self._log("✅ Objective achieved!", "SUCCESS")
                    break
                
                # Parse the strategy command
                command = strategy.get("command", "")
                await self._log(f"📋 Strategy: {command[:200]}...", "STRATEGY")
                
                # ═══════════════════════════════════════════════════
                # STEP 2: EXECUTE AI-DIRECTED TOOLS
                # ═══════════════════════════════════════════════════
                await self._set_status("attacking")
                
                tools_to_run = self._parse_tools_from_strategy(command)
                
                if not tools_to_run:
                    # Fallback: run default recon tools
                    tools_to_run = ["nmap"] if iteration == 1 else ["nuclei"]
                    await self._log(f"⚠️ No tools parsed, using fallback: {tools_to_run}", "WARN")
                else:
                    await self._log(f"🔧 Running tools: {tools_to_run}", "INFO")
                
                # Execute tools in parallel
                results = await self.orchestrator.run_parallel(self.target, tools_to_run)
                
                # ═══════════════════════════════════════════════════
                # STEP 3: PROCESS RESULTS
                # ═══════════════════════════════════════════════════
                await self._set_status("analyzing")
                
                new_findings = []
                for result in results:
                    if result.success:
                        new_findings.extend(result.findings)
                        await self._log(
                            f"✓ {result.tool_name}: {len(result.findings)} findings",
                            "SUCCESS" if result.findings else "INFO"
                        )
                    else:
                        await self._log(
                            f"✗ {result.tool_name}: {result.errors[0][:100] if result.errors else 'Failed'}",
                            "ERROR"
                        )
                
                # Log significant findings
                for finding in new_findings:
                    if finding.get("severity") in ["critical", "high"]:
                        await self._log(
                            f"🔥 [{finding['severity'].upper()}] {finding.get('name', 'Finding')}",
                            finding['severity'].upper()
                        )
                
                # Update context for next iteration
                self.findings.extend(new_findings)
                self.context = {
                    "target": self.target,
                    "phase": self._determine_phase(),
                    "findings": [
                        {"type": f.get("type"), "severity": f.get("severity"), "name": f.get("name")}
                        for f in self.findings[-20:]  # Last 20 findings for context
                    ],
                    "total_findings": len(self.findings),
                    "iteration": iteration,
                    "previous_command": command
                }
                
                # Brief pause between iterations
                await asyncio.sleep(2)
            
            # Attack complete
            await self._log_completion()
            
        except asyncio.CancelledError:
            await self._log("⏹️ Attack cancelled by operator", "WARN")
        except Exception as e:
            self.logger.error(f"Attack failed: {e}", exc_info=True)
            await self._log(f"💥 Attack error: {str(e)}", "ERROR")
        finally:
            self.is_active = False
            await self._set_status("idle")
    
    def _parse_tools_from_strategy(self, command: str) -> List[str]:
        """
        Extract tool names from AI strategy command.
        
        War Room Engineer outputs JSON: {"tools": ["nmap", "nuclei"], "reasoning": "..."}
        Falls back to text matching if JSON parse fails.
        """
        import json
        
        available_tools = self.orchestrator.get_available_tools()
        
        # Try parsing as JSON first (new format)
        try:
            # Find JSON in the response
            start = command.find('{')
            end = command.rfind('}') + 1
            if start != -1 and end > start:
                json_str = command[start:end]
                parsed = json.loads(json_str)
                
                if "tools" in parsed and isinstance(parsed["tools"], list):
                    # Validate tools against available list
                    valid_tools = [t for t in parsed["tools"] if t in available_tools]
                    if valid_tools:
                        self.logger.info(f"Parsed tools from JSON: {valid_tools}")
                        return valid_tools[:8]  # Max 8 tools (2 workers spare)
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.debug(f"JSON parse failed, using text matching: {e}")
        
        # Fallback: text-based matching
        found_tools = []
        command_lower = command.lower()
        
        for tool in available_tools:
            if tool in command_lower:
                found_tools.append(tool)
        
        # Common synonyms
        if "port scan" in command_lower or "port-scan" in command_lower:
            if "nmap" not in found_tools:
                found_tools.append("nmap")
        if "vulnerability" in command_lower or "vuln" in command_lower:
            if "nuclei" not in found_tools:
                found_tools.append("nuclei")
        if "sql injection" in command_lower or "sqli" in command_lower:
            if "sqlmap" not in found_tools:
                found_tools.append("sqlmap")
        
        # Deduplicate and limit
        return list(set(found_tools))[:8]

    
    def _determine_phase(self) -> str:
        """Determine current attack phase based on findings."""
        has_ports = any(f.get("type") == "port_scan" for f in self.findings)
        has_vulns = any(f.get("type") in ["vulnerability", "sqli", "rce"] for f in self.findings)
        has_creds = any(f.get("type") == "credential" for f in self.findings)
        has_shell = any(f.get("type") == "shell" for f in self.findings)
        
        if has_shell:
            return "POST_EXPLOIT"
        if has_creds:
            return "EXPLOIT"
        if has_vulns:
            return "EXPLOIT"
        if has_ports:
            return "VULN_SCAN"
        return "RECON"
    
    async def quick_attack(self, target: str):
        """Quick scan without full AI loop."""
        self.target = self._sanitize_target(target)
        self.is_active = True
        
        await self._set_status("quick_scan")
        await self._log(f"⚡ Quick scan: {self.target}", "INFO")
        
        try:
            # Just run quick nmap + nuclei
            results = await self.orchestrator.run_parallel(
                self.target, 
                ["nmap", "nuclei"]
            )
            
            for result in results:
                await self._log(
                    f"{'✓' if result.success else '✗'} {result.tool_name}: {len(result.findings)} findings",
                    "SUCCESS" if result.success else "ERROR"
                )
            
            await self._log("Quick scan complete", "SUCCESS")
            
        except Exception as e:
            await self._log(f"Quick scan failed: {e}", "ERROR")
        finally:
            self.is_active = False
            await self._set_status("idle")
    
    async def _log_completion(self):
        """Log attack completion summary."""
        critical = sum(1 for f in self.findings if f.get("severity") == "critical")
        high = sum(1 for f in self.findings if f.get("severity") == "high")
        
        summary = (
            f"━━━ ATTACK COMPLETE ━━━\n"
            f"Target: {self.target}\n"
            f"Findings: {len(self.findings)} total\n"
            f"  Critical: {critical}\n"
            f"  High: {high}"
        )
        await self._log(summary, "SUCCESS")
    
    def _sanitize_target(self, target: str) -> str:
        """Clean target input."""
        clean = target.strip()
        if clean.startswith("http://"):
            clean = clean[7:]
        elif clean.startswith("https://"):
            clean = clean[8:]
        return clean.rstrip('/').split('/')[0]
    
    async def _set_status(self, status: str):
        """Update agent status in TUI."""
        await self.bus.publish("swarm:status", {
            "agent_id": self.id,
            "status": status
        })
    
    async def _log(self, message: str, category: str = "INFO"):
        """Log to TUI kill chain panel."""
        await self.bus.publish("swarm:log", {
            "agent_id": self.id,
            "category": category,
            "message": message,
            "timestamp": "now"
        })
        # Also log to brain stream for important messages
        if category in ["STRATEGY", "THINKING", "ERROR", "CRITIC"]:
            await self.bus.publish("swarm:brain", {
                "category": category,
                "text": message
            })
    
    def pause(self):
        """Pause the attack."""
        self.is_active = False
    
    def resume(self):
        """Resume the attack."""
        self.is_active = True
    
    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "id": self.id,
            "target": self.target,
            "is_active": self.is_active,
            "phase": self.phase,
            "findings_count": len(self.findings)
        }
