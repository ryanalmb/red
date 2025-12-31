"""
Base Tool Adapter - Abstract base class for all security tool adapters.

Provides:
- Common error handling with retries
- Output parsing interface
- Standardized result format
- Logging and event bus integration
"""
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time


@dataclass
class ToolResult:
    """Standardized result from any security tool."""
    
    tool_name: str
    success: bool
    raw_output: str
    parsed_data: Dict[str, Any]
    findings: List[Dict[str, Any]]
    errors: List[str]
    execution_time: float
    command: str = ""
    
    @property
    def has_findings(self) -> bool:
        """Check if any findings were discovered."""
        return len(self.findings) > 0
    
    @property
    def critical_findings(self) -> List[Dict[str, Any]]:
        """Get only critical severity findings."""
        return [f for f in self.findings if f.get("severity") == "critical"]
    
    @property
    def high_findings(self) -> List[Dict[str, Any]]:
        """Get only high severity findings."""
        return [f for f in self.findings if f.get("severity") == "high"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "command": self.command,
            "execution_time": self.execution_time,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "errors": self.errors
        }


class BaseToolAdapter(ABC):
    """
    Abstract base class for all tool adapters.
    
    Provides common functionality for executing security tools,
    parsing output, handling errors, and standardizing results.
    """
    
    def __init__(self, worker_pool, retries: int = 3, timeout: float = 300.0,
                 event_bus=None):
        """
        Initialize the adapter.
        
        Args:
            worker_pool: WorkerPool instance for container execution
            retries: Number of retry attempts on failure
            timeout: Command execution timeout in seconds
            event_bus: Optional EventBus for publishing status updates
        """
        self.worker_pool = worker_pool
        self.retries = retries
        self.timeout = timeout
        self.bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Name of the tool this adapter wraps."""
        pass
    
    @property
    def tool_description(self) -> str:
        """Brief description of what the tool does."""
        return f"{self.tool_name} security tool"
    
    @abstractmethod
    def build_command(self, target: str, **options) -> str:
        """
        Build the CLI command for this tool.
        
        Args:
            target: The target (IP, URL, hostname)
            **options: Tool-specific options
            
        Returns:
            Complete CLI command string
        """
        pass
    
    @abstractmethod
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """
        Parse raw command output into structured data.
        
        Args:
            raw_output: Raw stdout from the command
            
        Returns:
            Parsed data as dictionary
        """
        pass
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract security findings from parsed data.
        
        Override in subclasses to provide tool-specific extraction.
        
        Default format for findings:
        {
            "type": "vulnerability|port|credential|etc",
            "severity": "critical|high|medium|low|info",
            "description": "Description of finding",
            "details": {...}
        }
        """
        return []
    
    def validate_target(self, target: str) -> bool:
        """
        Validate the target format.
        
        Override for tool-specific validation.
        """
        return bool(target and target.strip())
    
    async def execute(self, target: str, **options) -> ToolResult:
        """
        Execute the tool with full error handling and retry logic.
        
        Args:
            target: The target to scan/attack
            **options: Tool-specific options
            
        Returns:
            ToolResult with parsed findings
        """
        if not self.validate_target(target):
            return ToolResult(
                tool_name=self.tool_name,
                success=False,
                raw_output="",
                parsed_data={},
                findings=[],
                errors=["Invalid target format"],
                execution_time=0.0
            )
        
        command = self.build_command(target, **options)
        start_time = time.time()
        
        # Log start to terminal stream
        self.logger.info(f"Executing: {command}")
        if self.bus:
            await self.bus.publish("swarm:terminal", {
                "source": self.tool_name.upper(),
                "text": f"⚡ Starting {self.tool_name} → {target}"
            })
            await self.bus.publish("swarm:terminal", {
                "source": self.tool_name.upper(),
                "text": f"$ {command[:100]}{'...' if len(command) > 100 else ''}"
            })
            await self.bus.publish("swarm:tool", {
                "tool": self.tool_name,
                "status": "started",
                "target": target
            })
        
        result = await self._execute_with_retry(command)
        execution_time = time.time() - start_time
        
        # Parse output if successful
        if "ERROR:" not in result:
            try:
                parsed = self.parse_output(result)
                findings = self.extract_findings(parsed)
                
                # Log completion to terminal stream
                if self.bus:
                    await self.bus.publish("swarm:terminal", {
                        "source": self.tool_name.upper(),
                        "text": f"✓ {self.tool_name} complete ({len(findings)} findings, {execution_time:.1f}s)"
                    })
                    # Show brief output preview
                    if len(result) > 0:
                        preview = result[:200].replace('\n', ' ')
                        await self.bus.publish("swarm:terminal", {
                            "source": self.tool_name.upper(),
                            "text": f"  Output: {preview}{'...' if len(result) > 200 else ''}"
                        })
                    await self.bus.publish("swarm:tool", {
                        "tool": self.tool_name,
                        "status": "complete",
                        "findings_count": len(findings)
                    })
                
                return ToolResult(
                    tool_name=self.tool_name,
                    success=True,
                    raw_output=result,
                    parsed_data=parsed,
                    findings=findings,
                    errors=[],
                    execution_time=execution_time,
                    command=command
                )
            except Exception as e:
                self.logger.error(f"Parse error: {e}")
                return ToolResult(
                    tool_name=self.tool_name,
                    success=True,  # Command succeeded, parsing failed
                    raw_output=result,
                    parsed_data={},
                    findings=[],
                    errors=[f"Parse error: {str(e)}"],
                    execution_time=execution_time,
                    command=command
                )
        
        # Command failed - log to terminal
        if self.bus:
            await self.bus.publish("swarm:terminal", {
                "source": self.tool_name.upper(),
                "text": f"✗ {self.tool_name} FAILED ({execution_time:.1f}s)"
            })
            await self.bus.publish("swarm:terminal", {
                "source": self.tool_name.upper(),
                "text": f"  Error: {result[:150]}"
            })
            await self.bus.publish("swarm:tool", {
                "tool": self.tool_name,
                "status": "failed",
                "error": result
            })
        
        return ToolResult(
            tool_name=self.tool_name,
            success=False,
            raw_output=result,
            parsed_data={},
            findings=[],
            errors=[result],
            execution_time=execution_time,
            command=command
        )

    
    async def _execute_with_retry(self, command: str) -> str:
        """Execute command with retry logic."""
        last_error = ""
        
        for attempt in range(self.retries):
            try:
                result = await asyncio.wait_for(
                    self.worker_pool.execute_task(command, self.tool_name),
                    timeout=self.timeout
                )
                
                if "ERROR:" not in result:
                    return result
                
                last_error = result
                self.logger.warning(f"Attempt {attempt + 1}/{self.retries} failed: {result[:100]}")
                
            except asyncio.TimeoutError:
                last_error = f"ERROR: Timeout after {self.timeout}s"
                self.logger.warning(f"Attempt {attempt + 1}/{self.retries} timed out")
                
            except Exception as e:
                last_error = f"ERROR: {str(e)}"
                self.logger.error(f"Attempt {attempt + 1}/{self.retries} exception: {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        return last_error
    
    async def quick_scan(self, target: str) -> ToolResult:
        """
        Perform a quick/fast scan if the tool supports it.
        
        Override in subclasses to provide tool-specific quick scans.
        """
        return await self.execute(target)
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """
        Perform a comprehensive/thorough scan if the tool supports it.
        
        Override in subclasses to provide tool-specific deep scans.
        """
        return await self.execute(target)
