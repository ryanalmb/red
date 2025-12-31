"""
Tool Orchestrator - Parallel execution of security tools.

Manages running multiple tools concurrently, aggregating results,
and providing unified access to all tool adapters.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass

from cyberred.core.worker_pool import WorkerPool
from cyberred.core.kill_chain import Phase
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult
from cyberred.mcp.nmap_adapter import NmapAdapter
from cyberred.mcp.nuclei_adapter import NucleiAdapter
from cyberred.mcp.sqlmap_adapter import SqlmapAdapter
from cyberred.mcp.hydra_adapter import HydraAdapter
from cyberred.mcp.ffuf_adapter import FfufAdapter
from cyberred.mcp.nikto_adapter import NiktoAdapter
from cyberred.mcp.recon_adapters import SubfinderAdapter, MasscanAdapter
from cyberred.mcp.generic_adapter import GenericAdapter


@dataclass
class ToolConfig:
    """Configuration for a tool adapter."""
    adapter_class: Type[BaseToolAdapter]
    default_timeout: float = 300.0
    default_retries: int = 3
    requires_url: bool = False
    requires_ip: bool = False


class ToolOrchestrator:
    """
    Orchestrates parallel execution of security tools.
    
    Provides:
    - Unified interface to all tool adapters
    - Parallel execution with result aggregation
    - Phase-based tool selection for kill chain
    - Dynamic tool loading and configuration
    """
    
    # Tool registry with configurations
    TOOL_REGISTRY: Dict[str, ToolConfig] = {
        "nmap": ToolConfig(NmapAdapter, 600.0, 2),
        "nuclei": ToolConfig(NucleiAdapter, 900.0, 2),
        "sqlmap": ToolConfig(SqlmapAdapter, 600.0, 2, requires_url=True),
        "hydra": ToolConfig(HydraAdapter, 1200.0, 2),
        "ffuf": ToolConfig(FfufAdapter, 600.0, 2, requires_url=True),
        "nikto": ToolConfig(NiktoAdapter, 900.0, 2),
        "subfinder": ToolConfig(SubfinderAdapter, 600.0, 2),
        "masscan": ToolConfig(MasscanAdapter, 300.0, 2, requires_ip=True),
    }
    
    def __init__(self, worker_pool: WorkerPool, event_bus=None):
        self.worker_pool = worker_pool
        self.bus = event_bus
        self.logger = logging.getLogger("ToolOrchestrator")
        
        # Initialize adapters
        self.adapters: Dict[str, BaseToolAdapter] = {}
        self._init_adapters()
        
        # Generic adapter for raw commands
        self.generic = GenericAdapter(worker_pool)
    
    def _init_adapters(self):
        """Initialize all registered tool adapters."""
        for tool_name, config in self.TOOL_REGISTRY.items():
            try:
                adapter = config.adapter_class(
                    self.worker_pool,
                    retries=config.default_retries,
                    timeout=config.default_timeout,
                    event_bus=self.bus
                )
                self.adapters[tool_name] = adapter
                self.logger.debug(f"Initialized adapter: {tool_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {tool_name}: {e}")
    
    def get_adapter(self, tool_name: str) -> Optional[BaseToolAdapter]:
        """Get a specific tool adapter by name."""
        return self.adapters.get(tool_name.lower())
    
    async def run_tool(self, tool_name: str, target: str, **options) -> ToolResult:
        """
        Run a single tool against a target.
        
        Args:
            tool_name: Name of the tool to run
            target: Target host/URL
            **options: Tool-specific options
            
        Returns:
            ToolResult from the adapter
        """
        adapter = self.get_adapter(tool_name)
        
        if not adapter:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                raw_output="",
                parsed_data={},
                findings=[],
                errors=[f"Unknown tool: {tool_name}"],
                execution_time=0.0
            )
        
        self.logger.info(f"Running {tool_name} against {target}")
        
        if self.bus:
            await self.bus.publish("orchestrator:tool_start", {
                "tool": tool_name,
                "target": target
            })
        
        result = await adapter.execute(target, **options)
        
        if self.bus:
            await self.bus.publish("orchestrator:tool_complete", {
                "tool": tool_name,
                "success": result.success,
                "findings_count": len(result.findings)
            })
        
        return result
    
    async def run_parallel(self, target: str, tools: List[str], 
                          **shared_options) -> List[ToolResult]:
        """
        Run multiple tools in parallel against a target.
        
        Args:
            target: Target host/URL
            tools: List of tool names to run
            **shared_options: Options passed to all tools
            
        Returns:
            List of ToolResults from all tools
        """
        self.logger.info(f"Running {len(tools)} tools in parallel against {target}")
        
        # Create tasks for each tool
        tasks = []
        for tool_name in tools:
            task = asyncio.create_task(
                self.run_tool(tool_name, target, **shared_options)
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolResult(
                    tool_name=tools[i],
                    success=False,
                    raw_output="",
                    parsed_data={},
                    findings=[],
                    errors=[str(result)],
                    execution_time=0.0
                ))
            else:
                processed_results.append(result)
        
        # Aggregate stats
        successful = sum(1 for r in processed_results if r.success)
        total_findings = sum(len(r.findings) for r in processed_results)
        
        self.logger.info(
            f"Parallel execution complete: {successful}/{len(tools)} tools succeeded, "
            f"{total_findings} total findings"
        )
        
        return processed_results
    
    async def run_phase_tools(self, target: str, phase: Phase, 
                             tools: List[str], context: Dict[str, Any] = None) -> List[ToolResult]:
        """
        Run tools appropriate for a kill chain phase.
        
        Args:
            target: Target host/URL
            phase: Current kill chain phase
            tools: List of tool names
            context: Attack context from kill chain
            
        Returns:
            List of ToolResults
        """
        self.logger.info(f"Running phase {phase.name} tools: {tools}")
        
        if self.bus:
            await self.bus.publish("orchestrator:phase_start", {
                "phase": phase.name,
                "tools": tools,
                "target": target
            })
        
        # Configure tools based on phase
        options = self._get_phase_options(phase, context)
        
        # Filter tools to only those we have adapters for
        available_tools = [t for t in tools if t in self.adapters]
        
        if not available_tools:
            self.logger.warning(f"No available adapters for requested tools: {tools}")
            # Fall back to generic execution
            return await self._run_generic_phase(target, phase, tools)
        
        results = await self.run_parallel(target, available_tools, **options)
        
        if self.bus:
            await self.bus.publish("orchestrator:phase_complete", {
                "phase": phase.name,
                "results_count": len(results),
                "findings_count": sum(len(r.findings) for r in results)
            })
        
        return results
    
    def _get_phase_options(self, phase: Phase, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get tool options appropriate for the phase."""
        options = {}
        
        if phase == Phase.RECON:
            # Quick scans for recon
            options["quick"] = True
        
        elif phase == Phase.ENUMERATION:
            # Service version detection
            options["version_detection"] = True
        
        elif phase == Phase.VULNERABILITY:
            # Focus on high/critical vulns
            options["severity"] = "critical,high"
        
        elif phase == Phase.EXPLOITATION:
            # More aggressive settings
            options["batch"] = True
            options["level"] = 3
        
        return options
    
    async def _run_generic_phase(self, target: str, phase: Phase, 
                                 tools: List[str]) -> List[ToolResult]:
        """Run generic commands for tools without adapters."""
        results = []
        
        # Basic commands for common tools
        generic_commands = {
            "nmap": f"nmap -sV -sC {target}",
            "nuclei": f"nuclei -u {target} -severity critical,high -json",
            "subfinder": f"subfinder -d {target} -silent",
            "nikto": f"nikto -h {target}",
            "whatweb": f"whatweb {target}",
            "whois": f"whois {target}",
            "dnsrecon": f"dnsrecon -d {target}",
        }
        
        tasks = []
        for tool in tools:
            if tool in generic_commands:
                cmd = generic_commands[tool]
                tasks.append(asyncio.create_task(
                    self.generic.execute(cmd, tool)
                ))
        
        if tasks:
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(raw_results):
                if isinstance(result, str):
                    results.append(ToolResult(
                        tool_name=tools[i] if i < len(tools) else "generic",
                        success="ERROR" not in result,
                        raw_output=result,
                        parsed_data={},
                        findings=[],
                        errors=[] if "ERROR" not in result else [result],
                        execution_time=0.0
                    ))
        
        return results
    
    async def smart_scan(self, target: str) -> Dict[str, List[ToolResult]]:
        """
        Perform an intelligent multi-phase scan.
        
        Automatically selects tools based on target characteristics.
        """
        results = {}
        
        # Phase 1: Quick Recon
        self.logger.info("Phase 1: Quick Reconnaissance")
        recon_tools = ["nmap", "subfinder"]
        results["recon"] = await self.run_parallel(target, recon_tools)
        
        # Analyze recon results to determine next tools
        has_web = any(
            any(p.get("service", "").lower() in ["http", "https", "web"] 
                for p in finding.get("ports", []))
            for result in results["recon"]
            for finding in result.findings
        )
        
        # Phase 2: Targeted Scanning
        self.logger.info("Phase 2: Targeted Scanning")
        scan_tools = []
        if has_web:
            scan_tools.extend(["nuclei", "nikto", "ffuf"])
        scan_tools.append("nmap")  # Deep service scan
        
        results["scanning"] = await self.run_parallel(target, scan_tools[:3])
        
        return results
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.adapters.keys())
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics about tool usage."""
        return {
            "available_tools": list(self.adapters.keys()),
            "total_adapters": len(self.adapters)
        }
