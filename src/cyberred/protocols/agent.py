"""Agent protocol for Cyber-Red.

This module defines the AgentProtocol interface that all Cyber-Red agents
must implement. Uses `typing.Protocol` for structural subtyping.

The protocol is marked `@runtime_checkable` to enable isinstance() checks
for validating agent implementations at runtime.

Per architecture (lines 788-792, 982-994):
- Protocols belong in `src/cyberred/protocols/`
- Core has no dependencies on agents (boundary rule)
- Protocols depend only on core.models

Usage:
    from cyberred.protocols import AgentProtocol
    
    class MyAgent:
        # Implement all protocol methods...
        pass
    
    agent = MyAgent()
    assert isinstance(agent, AgentProtocol)
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from cyberred.core.models import AgentAction


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for all Cyber-Red agents.
    
    All agent implementations must satisfy this interface to be 
    compatible with the Cyber-Red orchestration layer. The protocol
    defines the core methods required for agent operation.
    
    Attributes:
        None (protocols define method signatures only)
    
    Methods:
        execute: Execute a task and return the resulting action.
        reason: Generate reasoning based on context signals.
        get_id: Return unique agent identifier.
        get_status: Return current agent status.
        get_decision_context: Return stigmergic signal IDs that influenced decisions.
        shutdown: Gracefully cleanup resources.
    
    Note:
        Implementations do NOT need to inherit from this class.
        Structural subtyping via Protocol means any class with
        matching method signatures is considered compliant.
    """
    
    async def execute(self, task: str) -> AgentAction:
        """Execute a task and return the resulting action.
        
        Args:
            task: Description of the task to execute.
            
        Returns:
            AgentAction recording what action was taken.
            
        Raises:
            ScopeViolationError: If task would violate scope constraints.
            KillSwitchTriggered: If kill switch is activated during execution.
        """
        ...
    
    async def reason(self, context: List[str]) -> str:
        """Generate reasoning based on stigmergic context signals.
        
        Args:
            context: List of stigmergic signal IDs to consider.
            
        Returns:
            String containing the agent's reasoning.
        """
        ...
    
    def get_id(self) -> str:
        """Return unique agent identifier.
        
        Returns:
            UUID-format string identifying this agent.
        """
        ...
    
    def get_status(self) -> str:
        """Return current agent status.
        
        Returns:
            Status string, one of: 'idle', 'active', 'waiting', 'shutdown'.
        """
        ...
    
    def get_decision_context(self) -> List[str]:
        """Return stigmergic signal IDs that influenced recent decisions.
        
        This is CRITICAL for NFR37 emergence validation. Every agent
        action must log which stigmergic signals influenced the decision.
        
        Returns:
            List of signal IDs from the stigmergic layer.
        """
        ...
    
    async def shutdown(self) -> None:
        """Gracefully cleanup resources and prepare for termination.
        
        Called when an engagement is paused, stopped, or the agent
        is being removed. Should release any held resources like
        Redis connections, pending tasks, etc.
        
        Returns:
            None
            
        Raises:
            Exception: Implementations should log errors but ideally suppress
            them to ensure cleanup continues, unless the error is critical.
        """
        ...
