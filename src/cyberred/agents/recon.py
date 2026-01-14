"""ReconAgent - Reconnaissance agent for discovery and enumeration.

This module implements the ReconAgent class which extends StigmergicAgent
to perform active reconnaissance using Kali tools. It coordinates via
stigmergic signals and adapts strategy based on Director guidance.

Configuration Options:
    The ReconAgent respects the following configuration from get_settings():
    
    - engagement.scope_path: Path to scope YAML file for target validation
    - agents.recon.timeout: Tool execution timeout (default: 300s)
    - agents.recon.parallel_scans: Max parallel scans (default: 3)
    
Example YAML configuration:
    agents:
      recon:
        tools:
          - nmap
          - masscan
          - whatweb
          - wafw00f
          - subfinder
        timeout: 300
        parallel_scans: 3
        llm_tier: STANDARD
"""

import asyncio
import uuid
import structlog
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timezone

from cyberred.agents.base import StigmergicAgent
from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction, Finding
from cyberred.tools.scope import ScopeValidator, ScopeConfig, ScopeViolationError
from cyberred.core.config import get_settings
from cyberred.tools.kali_executor import kali_execute
from cyberred.tools.output import OutputProcessor
from cyberred.tools.parsers.nmap import nmap_parser

log = structlog.get_logger().bind(component="recon_agent")

class ReconAgent(StigmergicAgent):
    """Reconnaissance agent for discovery and enumeration.
    
    Extends StigmergicAgent to perform active reconnaissance using Kali tools.
    Coordinates via stigmergic signals and adapts strategy based on Director guidance.
    
    Attributes:
        agent_id (str): Unique identifier for the agent.
        engagement_id (str): Engagement identifier.
        target (str): Target IP, hostname, or CIDR.
        event_bus (EventBus): Pub/sub system for stigmergic communication.
        current_strategy (str): Current scan intensity ('standard', 'stealth', 'aggressive').
        
    Usage:
        >>> agent = ReconAgent(
        ...     agent_id="recon-1",
        ...     engagement_id="eng-123",
        ...     target="example.com",
        ...     event_bus=event_bus
        ... )
        >>> await agent.spawn()
        >>> findings = await agent.execute_recon()
    """

    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        target: str,
        event_bus: EventBus,
        *args,
        **kwargs
    ):
        """Initialize ReconAgent.

        Args:
            agent_id: Unique agent identifier.
            engagement_id: Engagement identifier.
            target: Target to scan (validated against scope).
            event_bus: EventBus instance.
            *args: Additional args for StigmergicAgent.
            **kwargs: Additional kwargs for StigmergicAgent.

        Raises:
            ScopeViolationError: If target is out of scope.
        """
        super().__init__(
            agent_name="ReconAgent",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            *args, 
            **kwargs
        )
        self.target = target
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id, target=target)
        self._validate_target(target)
        
        self.output_processor = OutputProcessor()
        self.output_processor.register_parser("nmap", nmap_parser)
        
        # New features
        self.current_strategy = "standard"
        self._finding_buffer: List[Dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    def _validate_target(self, target: str) -> None:
        """Validate target against engagement scope."""
        validator = self._get_scope_validator()
        validator.validate(target=target)

    def _get_scope_validator(self) -> ScopeValidator:
        """Load scope validator from configured file."""
        settings = get_settings()
        path = settings.engagement.scope_path
        if path:
            try:
                return ScopeValidator.from_file(path)
            except Exception as e:
                self._log.warning("failed_to_load_scope_file", path=path, error=str(e))
        return ScopeValidator(ScopeConfig())

    async def execute_recon(self) -> tuple[List[Finding], List[AgentAction]]:
        """Execute reconnaissance workflow against target.

        Runs a sequence of tools (masscan, nmap, etc.) to enumerate the target.
        Adapts execution based on `current_strategy` and respects cancellation.
        
        Per NFR37: Every action creates an AgentAction with decision_context
        tracking which stigmergic signals influenced the decision.
        
        Returns:
            tuple[List[Finding], List[AgentAction]]: Discovered findings and action records.
            
        Example:
            >>> findings, actions = await agent.execute_recon()
            >>> for action in actions:
            ...     assert action.decision_context  # NFR37: must not be empty
        """
        all_findings: List[Finding] = []
        all_actions: List[AgentAction] = []
        
        tool_sequence: List[str] = [
            "masscan", "nmap", "whatweb", "wafw00f", "subfinder"
        ]

        for tool_name in tool_sequence:
            # Shutdown check
            if self._stop_event.is_set():
                self._log.info("recon_stopped_gracefully", tool=tool_name)
                break

            # Capture decision context BEFORE action (NFR37)
            decision_context = self.get_decision_context().copy()
            # Ensure non-empty decision_context per NFR37
            if not decision_context:
                decision_context = [f"initial_spawn:{self.agent_id}"]
            
            action_id = str(uuid.uuid4())
            result_finding_id: Optional[str] = None
            
            try:
                cmd = self._generate_tool_command(tool_name, self.target)
                if not cmd:
                    continue

                self._log.info("executing_tool", tool=tool_name, command=cmd[:50], strategy=self.current_strategy)
                
                # Execute
                result = await kali_execute(cmd)
                
                if not result.success:
                    self._log.warning("tool_execution_failed", tool=tool_name, error=result.stderr)
                
                # Parse
                processed = self.output_processor.process(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    tool=tool_name,
                    exit_code=result.exit_code,
                    agent_id=str(self.agent_id),
                    target=self.target,
                    error_type=result.error_type
                )
                
                # Publish findings
                for finding in processed.findings:
                    await self.on_finding(self.target, finding.type, finding.model_dump())
                    all_findings.append(finding)
                    # Track first finding ID for action record
                    if result_finding_id is None:
                        result_finding_id = finding.id
                
            except Exception as e:
                self._log.error("critical_tool_failure", tool=tool_name, error=str(e))
            
            # Create AgentAction record (NFR37: 100% decision_context population)
            action = AgentAction(
                id=action_id,
                agent_id=str(self.agent_id),
                action_type=f"recon:{tool_name}",
                target=self.target,
                timestamp=datetime.now(timezone.utc).isoformat(),
                decision_context=decision_context,
                result_finding_id=result_finding_id
            )
            all_actions.append(action)
            self._log.debug("action_recorded", action_id=action_id, tool=tool_name, 
                          decision_context_count=len(decision_context))
       
        return all_findings, all_actions
    
    def _generate_tool_command(self, tool_name: str, target: str) -> str:
        """Generate command for specified tool.
        
        Args:
            tool_name: Name of the tool (masscan, nmap, etc.)
            target: Target to scan.
            
        Returns:
            Command string, or empty string if tool unknown.
        """
        if tool_name == "masscan":
            return self._generate_masscan_command(target)
        elif tool_name == "nmap":
            return self._generate_nmap_command(target)
        elif tool_name == "whatweb":
            return self._generate_whatweb_command(target)
        elif tool_name == "wafw00f":
            return self._generate_wafw00f_command(target)
        elif tool_name == "subfinder":
            return self._generate_subfinder_command(target)
        return ""

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self._stop_event.set()
        self._log.info("agent_stopping")

    def _generate_nmap_command(self, target: str) -> str:
        """Generate nmap command based on strategy."""
        timing = "-T3" # standard
        if self.current_strategy == "aggressive":
            timing = "-T4"
        elif self.current_strategy == "stealth":
            timing = "-T2"
        return f"nmap {timing} -sV -oX - {target}"

    def _generate_masscan_command(self, target: str) -> str:
        """Generate masscan command based on strategy."""
        rate = "1000" # standard
        if self.current_strategy == "aggressive":
            rate = "10000"
        elif self.current_strategy == "stealth":
            rate = "100"
        return f"masscan -p1-65535 {target} --rate={rate}"
    
    def _generate_whatweb_command(self, target: str) -> str:
        """Generate whatweb command based on strategy."""
        args = ""
        if self.current_strategy == "aggressive":
            args = "--aggression=3"
        elif self.current_strategy == "stealth":
            args = "--aggression=1"
        return f"whatweb {args} {target}"

    def _generate_wafw00f_command(self, target: str) -> str:
        """Generate wafw00f command."""
        return f"wafw00f {target}"

    def _generate_subfinder_command(self, target: str) -> str:
        """Generate subfinder command."""
        return f"subfinder -d {target}"
    
    async def on_finding(self, target_hash: str, finding_type: str, content: Dict[str, Any]) -> None:
        """Publish finding to event bus.
        
        Buffers findings if connection is lost (degraded mode).
        
        Args:
            target_hash: Hash of the target.
            finding_type: Type of finding (e.g. 'open_port').
            content: Finding content dict.
        """
        channel = f"findings:{target_hash}:{finding_type}"
        message = {
            "agent_id": str(self.agent_id),
            "engagement_id": self.engagement_id,
            "data": content
        }
        
        # Flush buffer first if possible
        if self._finding_buffer:
             await self._flush_buffer()

        try:
            await self.event_bus.publish(channel, message)
        except Exception as e:
            self._log.warning("publish_failed_buffering", error=str(e), channel=channel)
            self._finding_buffer.append({"channel": channel, "message": message})

    async def _flush_buffer(self) -> None:
        """Attempt to flush buffered findings."""
        remaining = []
        for item in self._finding_buffer:
            try:
                await self.event_bus.publish(item["channel"], item["message"])
            except Exception:
                 remaining.append(item)
        
        if len(remaining) < len(self._finding_buffer):
             self._log.info("buffer_flushed", count=len(self._finding_buffer)-len(remaining))
        
        self._finding_buffer = remaining

    async def on_signal(self, channel: str, data: Dict[str, Any]) -> None:
        """Handle incoming stigmergic signals.
        
        Updates strategy if a 'strategies' channel message is received.
        """
        await super().on_signal(channel, data)
        if "strategies" in channel:
             strategy = data.get("strategy")
             if strategy in ["stealth", "standard", "aggressive"]:
                 self._log.info("strategy_updated", old=self.current_strategy, new=strategy)
                 self.current_strategy = strategy
