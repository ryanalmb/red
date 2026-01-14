"""Base agent class for Cyber-Red stigmergic coordination.

This module implements the StigmergicAgent base class which extends the
swarms.Agent to add P2P coordination capabilities via Redis Pub/Sub.
"""

import asyncio
import time
from typing import List, Optional, Any, Dict, TYPE_CHECKING

from swarms import Agent
import structlog

from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction
from cyberred.core.config import get_settings
from cyberred.core.exceptions import ThrottleTimeoutError

if TYPE_CHECKING:
    pass  # For future type hints if needed

log = structlog.get_logger().bind(component="stigmergic_agent")

class StigmergicAgent(Agent):
    """Base agent with stigmergic pub/sub hooks.
    
    Extends the swarms.Agent to provide hooks for:
    - Publishing findings to the swarm
    - Reacting to signals from other agents
    - coordinating via the EventBus
    """

    def __init__(
        self, 
        agent_name: str,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        *args, 
        **kwargs
    ):
        """Initialize the StigmergicAgent.

        Args:
            agent_name: Human readable name.
            agent_id: Unique identifier for this agent instance.
            engagement_id: ID of the current engagement.
            event_bus: EventBus instance for communication.
            *args: Passthrough to swarms.Agent
            **kwargs: Passthrough to swarms.Agent (llm, system_prompt, etc.)
        """
        # Ensure name is passed to swarms.Agent
        kwargs['agent_name'] = agent_name
        # Provide defaults for required swarms params if not present, to avoid super() errors
        if 'llm' not in kwargs and not args:
             # This might be risky if swarms validates strictly, but we assume caller provides it 
             # or we handle it. pure base class might be instantiated with mocks.
             pass

        super().__init__(*args, **kwargs)
        
        self.agent_id = agent_id
        self.engagement_id = engagement_id
        self.event_bus = event_bus
        self._decision_context: List[str] = []
        self._status = "idle"
        # Bind context for structured logging per architecture requirement
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._throttle_monitor_task: Optional[asyncio.Task[None]] = None

    async def spawn(self):
        """Initialize async components and subscriptions."""
        await self._setup_subscriptions()
        await self._start_throttle_monitor()
        self._status = "active"
        self._log.info("agent_spawned", status="active")

    async def _setup_subscriptions(self):
        """Subscribe to relevant stigmergic channels."""
        # Subscribe to findings wildcard
        await self.event_bus.subscribe("findings:*", self._handle_message)
        # Subscribe to strategy updates for this engagement
        await self.event_bus.subscribe(f"strategies:{self.engagement_id}", self._handle_message)
        # Subscribe to kill switch
        await self.event_bus.subscribe("control:kill", self._handle_message)
        
    async def _handle_message(self, channel: str, message: str):
        """Internal callback for EventBus subscriptions.
        
        Deserializes message and dispatches to on_signal.
        
        Args:
            channel: The channel the message was received on.
            message: The raw message string (may be JSON or plain text).
        """
        # Guard against None/empty messages
        if message is None:
            self._log.warning("null_message_received", channel=channel)
            return
            
        try:
            import json
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # If not JSON, wrap in dict for consistency with on_signal(channel, data: Dict)
                data = {"raw_content": message}
            
            await self.on_signal(channel, data)
        except Exception as e:
            self._log.error("message_handling_error", channel=channel, error=str(e), exc_info=True)

    async def on_finding(self, target_hash: str, finding_type: str, content: Dict[str, Any]):
        """Publish a finding to the swarm.
        
        Args:
            target_hash: Hash of the target (host/service).
            finding_type: Type of finding (e.g., 'sqli', 'open_port').
            content: The finding data.
        """
        channel = f"findings:{target_hash}:{finding_type}"
        message = {
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "data": content
        }
        await self.event_bus.publish(channel, message)
        self._log.info("finding_published", channel=channel, finding_type=finding_type)

    async def on_signal(self, channel: str, data: Dict[str, Any]):
        """Handle incoming stigmergic signal.
        
        Override this in subclasses to react to specific signals.
        
        Args:
            channel: The channel the signal was received on.
            data: The signal payload.
        """
        self._log.debug("signal_received", channel=channel)
        # Base implementation tracking decision context if present in data
        if "signal_id" in data:
            self._decision_context.append(data["signal_id"])

    async def on_complete(self, status: str, result: Dict[str, Any]):
        """Publish completion status.
        
        Args:
            status: Completion status (e.g. 'success', 'failed').
            result: Result data.
        """
        channel = f"agents:{self.agent_id}:status"
        message = {
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "status": status,
            "result": result
        }
        await self.event_bus.publish(channel, message)
        self._status = "idle"

    # AgentProtocol Implementation

    async def execute(self, task: str) -> AgentAction:
        """Execute a task using the underlying swarms Agent.
        
        This base implementation returns a stub AgentAction. Subclasses
        should override to integrate with swarms.Agent.run() or custom
        execution logic.
        
        Args:
            task: The task description to execute.
            
        Returns:
            AgentAction representing the execution result.
            
        Raises:
            Exception: Re-raises any execution errors after setting error status.
        """
        self._status = "active"
        
        # Check throttling (Story 7.2)
        try:
            is_throttled = await self._check_throttle()
            if is_throttled:
                self._status = "waiting"
                self._log.info("task_execution_throttled", task=task[:100] if task else None)
                
                settings = get_settings()
                max_wait = settings.agents.throttle.max_wait
                interval = settings.agents.throttle.check_interval
                start_wait = time.monotonic()
                
                while is_throttled:
                    if time.monotonic() - start_wait > max_wait:
                        raise ThrottleTimeoutError(
                            agent_id=self.agent_id,
                            wait_time=max_wait
                        )
                    
                    await asyncio.sleep(interval)
                    is_throttled = await self._check_throttle()
                
                self._status = "active"
                self._log.info("task_execution_resumed")
                
        except ThrottleTimeoutError:
            # Re-raise throttle timeout - this should not be swallowed
            raise
        except Exception as e:
            # Other errors in throttle logic -> log and proceed (Fail Open)
            self._log.error("throttle_logic_error", error=str(e))

        self._log.info("task_execution_started", task=task[:100] if task else None)
        
        try:
            # Base class returns a stub AgentAction.
            # Subclasses (e.g., GhostAgent) override this to call swarms.Agent.run()
            # and transform results into proper AgentAction instances.
            import uuid
            import datetime
            return AgentAction(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                action_type="execute",
                target=task,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
        except Exception as e:
            self._status = "error"
            self._log.error("task_execution_failed", error=str(e))
            raise

    async def reason(self, context: List[str]) -> str:
        """Generate reasoning."""
        # Simple base implementation
        return f"Reasoning based on {len(context)} signals."

    def get_id(self) -> str:
        return self.agent_id

    def get_status(self) -> str:
        return self._status

    def get_decision_context(self) -> List[str]:
        """Return the list of signal IDs that influenced this agent's decisions.
        
        This method supports NFR37 (Emergence Validation) by providing
        an audit trail of stigmergic signals that contributed to the
        agent's reasoning and actions.
        
        Returns:
            List of signal_id strings from received stigmergic signals.
        """
        return self._decision_context

    async def shutdown(self) -> None:
        """Cleanup resources."""
        self._status = "shutdown"
        if self._throttle_monitor_task:
            self._throttle_monitor_task.cancel()
            try:
                await self._throttle_monitor_task
            except Exception:
                pass
            self._throttle_monitor_task = None
        # Unsubscribe if needed
        self._log.info("agent_shutdown")

    async def _start_throttle_monitor(self):
        """Start the background throttle monitoring task."""
        if self._throttle_monitor_task is None:
            self._throttle_monitor_task = asyncio.create_task(self._throttle_monitor_loop())

    async def _throttle_monitor_loop(self):
        """Monitor throttle status and log transitions."""
        last_throttle_state = False
        
        while self._status != "shutdown":
            try:
                # Get check interval from settings
                settings = get_settings()
                interval = settings.agents.throttle.check_interval
                
                is_throttled = await self._check_throttle()
                
                if is_throttled and not last_throttle_state:
                    self._log.info("agent_throttled", queue_depth=get_settings().agents.throttle.threshold) # Approximation for log, actual depth inside check
                    # To allow monitoring, maybe `_check_throttle` should return status or we inspect gateway again?
                    # For now just log event.
                elif not is_throttled and last_throttle_state:
                    self._log.info("agent_unthrottled")
                    
                last_throttle_state = is_throttled
                
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("throttle_monitor_error", error=str(e))
                await asyncio.sleep(5.0) # Backoff on error

    async def _check_throttle(self) -> bool:
        """Check if agent should throttle execution.
        
        Logic:
        1. Get current queue depth from LLMGateway.
        2. Get throttle configuration (threshold).
        3. If threshold < 1.0, calculate max capacity based on `engagement.max_agents`.
           - This assumes max_agents is a rough proxy for "full load".
           - Threshold becomes `threshold * max_agents`.
        4. If threshold >= 1.0, use as raw count.
        5. Return True if queue_depth >= threshold.
        
        Fail-open: If gateway unavailable, return False.
        
        Returns:
            True if should throttle, False otherwise.
        """
        try:
            # Import here to avoid top-level circular imports
            from cyberred.llm.gateway import get_gateway
            
            gateway = get_gateway()
            queue_depth = gateway.queue_depth
            
            settings = get_settings()
            throttle_config = settings.agents.throttle
            
            threshold = throttle_config.threshold
            
            # Normalize threshold
            if threshold < 1.0:
                max_agents = settings.engagement.max_agents
                # Ensure at least 1 if max_agents is small
                target_depth = max(1, int(threshold * max_agents))
            else:
                target_depth = int(threshold)
                
            return queue_depth >= target_depth
            
        except Exception as e:
            # Fail-open strategy
            self._log.warning("throttle_check_failed", error=str(e))
            return False
