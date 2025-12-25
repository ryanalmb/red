"""
Ghost Agent - Autonomous attack agent with Kill Chain progression.

The Ghost Agent is the autonomous entity that executes attacks
following the Cyber Kill Chain methodology with AI-guided decision making.
"""
import asyncio
import logging
from typing import Optional

from src.core.council import CouncilOfExperts
from src.core.kill_chain import KillChain, Phase
from src.core.tool_orchestrator import ToolOrchestrator
from src.core.event_bus import EventBus


class GhostAgent:
    """
    Autonomous attack agent with kill chain progression.
    
    Features:
    - Full kill chain execution (RECON → EXFIL)
    - AI-guided strategy via War Room
    - Parallel tool execution
    - Learning from failures with fallback strategies
    """
    
    def __init__(self, agent_id: int, council: CouncilOfExperts, 
                 tool_orchestrator: ToolOrchestrator, event_bus: EventBus):
        self.id = agent_id
        self.council = council
        self.orchestrator = tool_orchestrator
        self.bus = event_bus
        self.logger = logging.getLogger(f"Agent-{agent_id}")
        
        # Attack state
        self.kill_chain: Optional[KillChain] = None
        self.target: Optional[str] = None
        self.is_active = False
    
    async def engage(self, target: str, max_phases: int = 10):
        """
        Full kill chain execution with parallel tool usage.
        
        Args:
            target: Target to attack
            max_phases: Maximum phases to execute
        """
        self.target = self._sanitize_target(target)
        self.is_active = True
        
        self.logger.info(f"Engaging target: {self.target}")
        await self._set_status("initializing")
        
        # Initialize kill chain
        self.kill_chain = KillChain(self.target, self.orchestrator, self.bus)
        
        # Track phase count
        phase_count = 0
        
        try:
            while (self.kill_chain.current_phase != Phase.COMPLETE and 
                   phase_count < max_phases and 
                   self.is_active):
                
                phase_count += 1
                current_phase = self.kill_chain.current_phase
                
                await self._set_status(f"phase_{current_phase.name.lower()}")
                await self._log(f"Phase {phase_count}: {current_phase.name}", "PHASE")
                
                # Execute phase
                result = await self.kill_chain.advance()
                
                await self._log(
                    f"Phase {result.phase.name}: {len(result.findings)} findings",
                    "PHASE"
                )
                
                # Log significant findings
                for finding in result.findings:
                    if finding.get("severity") in ["critical", "high"]:
                        await self._log(
                            f"[{finding['severity'].upper()}] {finding.get('name')}: {finding.get('description', '')[:100]}",
                            finding['severity'].upper()
                        )
                
                # Get AI strategy for next phase if not complete
                if result.next_phase and result.next_phase != Phase.COMPLETE:
                    await self._get_ai_guidance(result)
                
                # Small delay between phases
                await asyncio.sleep(1)
            
            # Execution complete
            await self._log_completion()
            
        except asyncio.CancelledError:
            await self._log("Attack cancelled by operator", "WARN")
        except Exception as e:
            self.logger.error(f"Attack failed: {e}")
            await self._log(f"Attack error: {str(e)}", "ERROR")
        finally:
            self.is_active = False
            await self._set_status("idle")
    
    async def quick_attack(self, target: str):
        """
        Quick attack without full kill chain.
        
        Performs quick recon + vuln scan only.
        """
        self.target = self._sanitize_target(target)
        self.is_active = True
        
        await self._set_status("quick_attack")
        await self._log(f"Quick attack on {self.target}", "INFO")
        
        try:
            # Run smart scan
            results = await self.orchestrator.smart_scan(self.target)
            
            # Log findings
            total_findings = 0
            for phase_name, phase_results in results.items():
                for result in phase_results:
                    total_findings += len(result.findings)
                    for finding in result.findings:
                        await self._log(
                            f"[{result.tool_name}] {finding.get('name', 'Finding')}",
                            finding.get("severity", "INFO").upper()
                        )
            
            await self._log(f"Quick attack complete: {total_findings} findings", "SUCCESS")
            
        except Exception as e:
            await self._log(f"Quick attack failed: {e}", "ERROR")
        finally:
            self.is_active = False
            await self._set_status("idle")
    
    async def _get_ai_guidance(self, phase_result):
        """Get AI strategy for next phase."""
        try:
            context = {
                "target": self.target,
                "phase": phase_result.phase.name,
                "next_phase": phase_result.next_phase.name if phase_result.next_phase else None,
                "findings": [
                    {"type": f.get("type"), "severity": f.get("severity"), "name": f.get("name")}
                    for f in phase_result.findings[:10]  # Limit context size
                ],
                "recommended_tools": phase_result.recommended_tools,
                "kill_chain_status": self.kill_chain.get_status()
            }
            
            strategy = await self.council.decide_attack(context)
            
            if strategy["status"] == "VETOED":
                await self._log(f"Strategy VETOED: {strategy['reason']}", "CRITIC")
                # Don't stop - just log the veto
            elif strategy["status"] == "APPROVED":
                await self._log(f"AI Strategy: {strategy.get('command', 'Continue')[:100]}", "STRATEGY")
                
        except Exception as e:
            self.logger.error(f"AI guidance failed: {e}")
            # Continue without AI guidance
    
    async def _log_completion(self):
        """Log attack completion summary."""
        if not self.kill_chain:
            return
        
        status = self.kill_chain.get_status()
        
        summary = (
            f"Kill chain complete for {self.target}\n"
            f"  Phases: {status['phases_completed']}\n"
            f"  Hosts: {status['discovered_hosts']}\n"
            f"  Ports: {status['open_ports']}\n"
            f"  Vulns: {status['vulnerabilities']}\n"
            f"  Creds: {status['credentials']}\n"
            f"  Shells: {status['shells']}"
        )
        
        await self._log(summary, "SUCCESS")
    
    def _sanitize_target(self, target: str) -> str:
        """Sanitize target input."""
        # Remove common wrapping
        clean = target.strip()
        
        # For domain-only operations, strip protocol
        if clean.startswith("http://"):
            clean = clean[7:]
        elif clean.startswith("https://"):
            clean = clean[8:]
        
        # Remove trailing slash
        clean = clean.rstrip('/')
        
        # Get just the host part if there's a path
        if '/' in clean:
            clean = clean.split('/')[0]
        
        return clean
    
    async def _set_status(self, status: str):
        """Update agent status in TUI."""
        await self.bus.publish("swarm:status", {
            "agent_id": self.id,
            "status": status
        })
    
    async def _log(self, message: str, category: str = "INFO"):
        """Log message to TUI."""
        await self.bus.publish("swarm:log", {
            "agent_id": self.id,
            "category": category,
            "message": message,
            "timestamp": "now"
        })
    
    def pause(self):
        """Pause the attack."""
        self.is_active = False
        self.logger.info("Attack paused")
    
    def resume(self):
        """Resume the attack."""
        self.is_active = True
        self.logger.info("Attack resumed")
    
    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "id": self.id,
            "target": self.target,
            "is_active": self.is_active,
            "current_phase": self.kill_chain.current_phase.name if self.kill_chain else None,
            "kill_chain_status": self.kill_chain.get_status() if self.kill_chain else None
        }
