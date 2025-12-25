"""
Kill Chain State Machine - Attack phase orchestration.

Implements the Cyber Kill Chain model for structured attack progression:
RECON → ENUMERATION → VULNERABILITY → EXPLOITATION → POST_EXPLOIT → EXFIL
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
import asyncio
import logging
from datetime import datetime


class Phase(Enum):
    """Kill Chain phases."""
    RECON = auto()           # Passive and active reconnaissance
    ENUMERATION = auto()     # Service and version enumeration
    VULNERABILITY = auto()   # Vulnerability scanning
    EXPLOITATION = auto()    # Active exploitation
    POST_EXPLOIT = auto()    # Maintain access, privilege escalation
    EXFIL = auto()          # Data extraction
    COMPLETE = auto()        # Mission complete


@dataclass
class PhaseResult:
    """Result from executing a kill chain phase."""
    phase: Phase
    success: bool
    findings: List[Dict[str, Any]] = field(default_factory=list)
    next_phase: Optional[Phase] = None
    recommended_tools: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    @property
    def has_critical_findings(self) -> bool:
        """Check if phase found critical severity issues."""
        return any(f.get("severity") == "critical" for f in self.findings)
    
    @property
    def has_high_findings(self) -> bool:
        """Check if phase found high severity issues."""
        return any(f.get("severity") == "high" for f in self.findings)


@dataclass
class AttackContext:
    """Accumulated intelligence from attack phases."""
    target: str
    discovered_hosts: Set[str] = field(default_factory=set)
    open_ports: Dict[str, List[int]] = field(default_factory=dict)
    services: Dict[str, Dict[int, str]] = field(default_factory=dict)
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    credentials: List[Dict[str, Any]] = field(default_factory=list)
    shells: List[Dict[str, Any]] = field(default_factory=list)
    phase_history: List[PhaseResult] = field(default_factory=list)
    
    def add_port(self, host: str, port: int, service: str = "unknown"):
        """Add discovered port."""
        if host not in self.open_ports:
            self.open_ports[host] = []
            self.services[host] = {}
        if port not in self.open_ports[host]:
            self.open_ports[host].append(port)
        self.services[host][port] = service
    
    def add_vulnerability(self, vuln: Dict[str, Any]):
        """Add discovered vulnerability."""
        self.vulnerabilities.append(vuln)
    
    def add_credential(self, cred: Dict[str, Any]):
        """Add discovered credential."""
        self.credentials.append(cred)
    
    def add_shell(self, shell: Dict[str, Any]):
        """Add obtained shell."""
        self.shells.append(shell)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AI context."""
        return {
            "target": self.target,
            "discovered_hosts": list(self.discovered_hosts),
            "open_ports": {h: list(p) for h, p in self.open_ports.items()},
            "services": dict(self.services),
            "vulnerabilities_count": len(self.vulnerabilities),
            "credentials_count": len(self.credentials),
            "shells_count": len(self.shells)
        }


class KillChain:
    """
    Manages attack progression through kill chain phases.
    
    Uses a state machine to orchestrate tool execution and
    determine next steps based on findings.
    """
    
    # Tools available for each phase
    PHASE_TOOLS: Dict[Phase, List[str]] = {
        Phase.RECON: ["subfinder", "masscan", "nmap", "whois", "dnsrecon"],
        Phase.ENUMERATION: ["nmap", "whatweb", "nikto", "enum4linux"],
        Phase.VULNERABILITY: ["nuclei", "nikto", "wpscan", "sslscan", "sqlmap"],
        Phase.EXPLOITATION: ["sqlmap", "metasploit", "crackmapexec", "hydra"],
        Phase.POST_EXPLOIT: ["crackmapexec", "impacket", "linpeas"],
        Phase.EXFIL: ["netcat", "curl", "scp"]
    }
    
    # Minimum findings to advance to next phase
    PHASE_THRESHOLDS = {
        Phase.RECON: 1,        # Need at least 1 port/host
        Phase.ENUMERATION: 1,  # Need at least 1 service
        Phase.VULNERABILITY: 0, # Can skip to exploit if confident
        Phase.EXPLOITATION: 1,  # Need a shell or credential
        Phase.POST_EXPLOIT: 1,  # Need elevated access
    }
    
    def __init__(self, target: str, tool_orchestrator, event_bus=None):
        self.target = target
        self.orchestrator = tool_orchestrator
        self.bus = event_bus
        self.current_phase = Phase.RECON
        self.context = AttackContext(target=target)
        self.logger = logging.getLogger("KillChain")
        self._phase_start_time = None
    
    async def advance(self) -> PhaseResult:
        """
        Execute current phase and determine next steps.
        
        Returns:
            PhaseResult with findings and next phase
        """
        self._phase_start_time = datetime.now()
        tools = self.PHASE_TOOLS.get(self.current_phase, [])
        
        self.logger.info(f"Executing phase: {self.current_phase.name}")
        
        if self.bus:
            await self.bus.publish("killchain:phase", {
                "phase": self.current_phase.name,
                "status": "started",
                "tools": tools
            })
        
        # Execute tools in parallel via orchestrator
        results = await self.orchestrator.run_phase_tools(
            self.target, 
            self.current_phase,
            tools,
            context=self.context.to_dict()
        )
        
        # Aggregate findings from all tools
        all_findings = []
        errors = []
        
        for tool_result in results:
            if tool_result.success:
                all_findings.extend(tool_result.findings)
                self._update_context(tool_result)
            else:
                errors.extend(tool_result.errors)
        
        # Determine next phase based on findings
        next_phase = self._determine_next_phase(all_findings)
        recommended = self._recommend_tools(next_phase, all_findings)
        
        execution_time = (datetime.now() - self._phase_start_time).total_seconds()
        
        result = PhaseResult(
            phase=self.current_phase,
            success=len(all_findings) > 0 or len(errors) == 0,
            findings=all_findings,
            next_phase=next_phase,
            recommended_tools=recommended,
            execution_time=execution_time,
            errors=errors
        )
        
        # Update state
        self.context.phase_history.append(result)
        self.current_phase = next_phase
        
        if self.bus:
            await self.bus.publish("killchain:phase", {
                "phase": result.phase.name,
                "status": "completed",
                "findings_count": len(all_findings),
                "next_phase": next_phase.name if next_phase else None
            })
        
        return result
    
    def _update_context(self, tool_result):
        """Update attack context with tool findings."""
        for finding in tool_result.findings:
            finding_type = finding.get("type", "")
            
            if finding_type == "port_scan":
                for port_info in finding.get("ports", []):
                    host = finding.get("host", self.target)
                    self.context.add_port(
                        host, 
                        int(port_info.get("port", 0)),
                        port_info.get("service", "unknown")
                    )
                    self.context.discovered_hosts.add(host)
            
            elif finding_type in ["vulnerability", "sqli", "rce"]:
                self.context.add_vulnerability(finding)
            
            elif finding_type == "credential":
                self.context.add_credential(finding)
            
            elif finding_type == "shell":
                self.context.add_shell(finding)
            
            elif finding_type == "recon":
                # Add discovered subdomains as potential hosts
                for subdomain in finding.get("subdomains", []):
                    self.context.discovered_hosts.add(subdomain)
    
    def _determine_next_phase(self, findings: List[Dict]) -> Phase:
        """
        Determine next phase based on findings.
        
        Uses a state machine with conditional transitions.
        """
        current = self.current_phase
        
        if current == Phase.RECON:
            # Move to enumeration if we found hosts/ports
            if len(self.context.open_ports) > 0 or len(self.context.discovered_hosts) > 0:
                return Phase.ENUMERATION
            # Stay in recon if nothing found yet
            return Phase.RECON
        
        elif current == Phase.ENUMERATION:
            return Phase.VULNERABILITY
        
        elif current == Phase.VULNERABILITY:
            # Move to exploitation if we found high/critical vulns
            if any(f.get("severity") in ["critical", "high"] for f in findings):
                return Phase.EXPLOITATION
            # Stay in vuln scanning if only found medium/low
            if any(f.get("severity") in ["medium", "low"] for f in findings):
                return Phase.VULNERABILITY
            # Nothing found, try exploitation anyway (with credentials)
            if len(self.context.credentials) > 0:
                return Phase.EXPLOITATION
            return Phase.VULNERABILITY
        
        elif current == Phase.EXPLOITATION:
            # Got shell? Move to post-exploit
            if any(f.get("type") == "shell" for f in findings):
                return Phase.POST_EXPLOIT
            # Got credentials? Keep exploiting different services
            if any(f.get("type") == "credential" for f in findings):
                return Phase.EXPLOITATION
            return Phase.EXPLOITATION
        
        elif current == Phase.POST_EXPLOIT:
            # After post-exploit, move to exfil
            return Phase.EXFIL
        
        elif current == Phase.EXFIL:
            return Phase.COMPLETE
        
        return Phase.COMPLETE
    
    def _recommend_tools(self, next_phase: Phase, findings: List[Dict]) -> List[str]:
        """Recommend specific tools based on context."""
        if next_phase == Phase.COMPLETE:
            return []
        
        base_tools = self.PHASE_TOOLS.get(next_phase, [])
        recommendations = []
        
        # Add context-aware recommendations
        if next_phase == Phase.VULNERABILITY:
            # Recommend based on services found
            services = self.context.services
            for host, port_services in services.items():
                for port, service in port_services.items():
                    service_lower = service.lower()
                    if "http" in service_lower or "web" in service_lower:
                        recommendations.extend(["nuclei", "nikto", "ffuf", "sqlmap"])
                    if "wordpress" in service_lower:
                        recommendations.append("wpscan")
                    if "ssl" in service_lower or "https" in service_lower:
                        recommendations.append("sslscan")
        
        elif next_phase == Phase.EXPLOITATION:
            # Recommend based on vulnerabilities
            for vuln in self.context.vulnerabilities:
                vuln_type = vuln.get("type", "")
                if vuln_type == "sqli":
                    recommendations.append("sqlmap")
                if "web" in vuln_type.lower():
                    recommendations.append("metasploit")
            
            # Add brute force if we have services
            if len(self.context.open_ports) > 0:
                recommendations.append("hydra")
        
        # Combine with base tools and deduplicate
        all_tools = list(set(base_tools + recommendations))
        return all_tools[:5]  # Limit to top 5
    
    def get_status(self) -> Dict[str, Any]:
        """Get current kill chain status."""
        return {
            "target": self.target,
            "current_phase": self.current_phase.name,
            "phases_completed": len(self.context.phase_history),
            "discovered_hosts": len(self.context.discovered_hosts),
            "open_ports": sum(len(p) for p in self.context.open_ports.values()),
            "vulnerabilities": len(self.context.vulnerabilities),
            "credentials": len(self.context.credentials),
            "shells": len(self.context.shells)
        }
    
    async def run_to_completion(self, max_phases: int = 10) -> List[PhaseResult]:
        """
        Run the kill chain to completion or max phases.
        
        Args:
            max_phases: Maximum number of phases to execute
            
        Returns:
            List of all phase results
        """
        results = []
        
        for _ in range(max_phases):
            if self.current_phase == Phase.COMPLETE:
                break
            
            result = await self.advance()
            results.append(result)
            
            self.logger.info(
                f"Phase {result.phase.name} complete: "
                f"{len(result.findings)} findings, "
                f"next: {result.next_phase.name if result.next_phase else 'DONE'}"
            )
        
        return results
