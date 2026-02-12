"""Engagement Statistics Aggregation.

This module provides statistics collection and aggregation for engagements,
supporting FR41 (engagement summary with key statistics).

Story 13.12: Engagement Summary Statistics
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

from cyberred.core.exceptions import EngagementNotFoundError
from cyberred.daemon.state_machine import EngagementState

if TYPE_CHECKING:
    from cyberred.daemon.session_manager import SessionManager
    from cyberred.storage.checkpoint import CheckpointManager
    from cyberred.llm.gateway import LLMGateway
    from cyberred.core.event_bus import EventBus


@dataclass
class EngagementStatistics:
    """Engagement summary statistics for reporting.
    
    Aggregates metrics from multiple subsystems to provide
    unified engagement outcome summary (FR41).
    
    Attributes:
        engagement_id: Unique engagement identifier.
        start_time: ISO 8601 UTC timestamp of engagement start.
        end_time: ISO 8601 UTC timestamp of engagement end (None if running).
        duration_seconds: Total engagement duration in seconds.
        total_agents_spawned: Total number of agents created.
        active_agents: Currently active agents.
        idle_agents: Currently idle agents.
        error_agents: Currently in error state.
        max_concurrent_agents: Peak concurrent agent count.
        findings_critical: Critical severity findings.
        findings_high: High severity findings.
        findings_medium: Medium severity findings.
        findings_low: Low severity findings.
        total_findings: Total findings across all severities.
        coverage_percent: Scope coverage percentage (0.0-100.0).
        tools_executed: Total tool invocations.
        successful_tools: Successful tool executions.
        failed_tools: Failed tool executions.
        llm_calls: Total LLM API calls.
        llm_tokens_input: Total input tokens consumed.
        llm_tokens_output: Total output tokens generated.
        emergence_score: Stigmergic emergence score (0.0-1.0), None if not calculated.
        emergence_threshold_met: True if emergence >= 20% (NFR35).
        engagement_state: Current engagement state.
        operator: Operator username.
    """
    
    engagement_id: str
    
    # Temporal metrics
    start_time: str
    end_time: str | None
    duration_seconds: int
    
    # Agent metrics
    total_agents_spawned: int
    active_agents: int
    idle_agents: int
    error_agents: int
    max_concurrent_agents: int
    
    # Finding metrics
    findings_critical: int
    findings_high: int
    findings_medium: int
    findings_low: int
    total_findings: int
    
    # Coverage and execution metrics
    coverage_percent: float
    tools_executed: int
    successful_tools: int
    failed_tools: int
    
    # LLM metrics
    llm_calls: int
    llm_tokens_input: int
    llm_tokens_output: int
    
    # Emergence metrics (optional)
    emergence_score: float | None
    emergence_threshold_met: bool
    
    # Additional context
    engagement_state: str
    operator: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "engagement_id": self.engagement_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "total_agents_spawned": self.total_agents_spawned,
            "active_agents": self.active_agents,
            "idle_agents": self.idle_agents,
            "error_agents": self.error_agents,
            "max_concurrent_agents": self.max_concurrent_agents,
            "findings": {
                "critical": self.findings_critical,
                "high": self.findings_high,
                "medium": self.findings_medium,
                "low": self.findings_low,
                "total": self.total_findings,
            },
            "coverage_percent": self.coverage_percent,
            "tools": {
                "executed": self.tools_executed,
                "successful": self.successful_tools,
                "failed": self.failed_tools,
            },
            "llm": {
                "calls": self.llm_calls,
                "tokens_input": self.llm_tokens_input,
                "tokens_output": self.llm_tokens_output,
            },
            "emergence": {
                "score": self.emergence_score,
                "threshold_met": self.emergence_threshold_met,
            } if self.emergence_score is not None else None,
            "engagement_state": self.engagement_state,
            "operator": self.operator,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngagementStatistics":
        """Create from dictionary.
        
        Args:
            data: Dictionary representation.
            
        Returns:
            EngagementStatistics instance.
        """
        findings = data.get("findings", {})
        tools = data.get("tools", {})
        llm = data.get("llm", {})
        emergence = data.get("emergence")
        
        return cls(
            engagement_id=data["engagement_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            duration_seconds=data["duration_seconds"],
            total_agents_spawned=data["total_agents_spawned"],
            active_agents=data["active_agents"],
            idle_agents=data["idle_agents"],
            error_agents=data["error_agents"],
            max_concurrent_agents=data["max_concurrent_agents"],
            findings_critical=findings.get("critical", 0),
            findings_high=findings.get("high", 0),
            findings_medium=findings.get("medium", 0),
            findings_low=findings.get("low", 0),
            total_findings=findings.get("total", 0),
            coverage_percent=data["coverage_percent"],
            tools_executed=tools.get("executed", 0),
            successful_tools=tools.get("successful", 0),
            failed_tools=tools.get("failed", 0),
            llm_calls=llm.get("calls", 0),
            llm_tokens_input=llm.get("tokens_input", 0),
            llm_tokens_output=llm.get("tokens_output", 0),
            emergence_score=emergence.get("score") if emergence else None,
            emergence_threshold_met=emergence.get("threshold_met", False) if emergence else False,
            engagement_state=data["engagement_state"],
            operator=data["operator"],
        )


class EngagementStatisticsAggregator:
    """Aggregates engagement statistics from multiple sources.
    
    Collects metrics from:
    - SessionManager (engagement state, timing)
    - CheckpointManager (findings, agent history)
    - LLM Gateway (LLM usage)
    - EmergenceMetrics (emergence score)
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        checkpoint_manager: CheckpointManager,
        llm_gateway: LLMGateway,
        event_bus: EventBus,
    ):
        """Initialize aggregator.
        
        Args:
            session_manager: Session manager for engagement context.
            checkpoint_manager: Checkpoint manager for persistent state.
            llm_gateway: LLM gateway for usage metrics.
            event_bus: Event bus for real-time metrics.
        """
        self.session_manager = session_manager
        self.checkpoint_manager = checkpoint_manager
        self.llm_gateway = llm_gateway
        self.event_bus = event_bus
        self._log = structlog.get_logger().bind(component="statistics_aggregator")
    
    async def get_statistics(
        self,
        engagement_id: str,
    ) -> EngagementStatistics:
        """Aggregate statistics for an engagement.
        
        Args:
            engagement_id: Engagement to collect statistics for.
            
        Returns:
            Complete engagement statistics.
            
        Raises:
            EngagementNotFoundError: If engagement doesn't exist.
        """
        # Get engagement context from SessionManager
        context = self.session_manager.get_engagement_or_raise(engagement_id)
        
        # Collect from multiple sources concurrently
        findings_task = self._get_finding_stats(engagement_id)
        agent_task = self._get_agent_stats(engagement_id, context)
        tools_task = self._get_tool_stats(engagement_id)
        llm_task = self._get_llm_stats(engagement_id)
        emergence_task = self._get_emergence_stats(engagement_id)
        
        findings, agents, tools, llm, emergence = await asyncio.gather(
            findings_task,
            agent_task,
            tools_task,
            llm_task,
            emergence_task,
        )
        
        # Calculate duration
        start_time = context.created_at
        
        # Determine end time based on state
        if context.state in (EngagementState.RUNNING, EngagementState.PAUSED, EngagementState.INITIALIZING):
            end_time = None
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        else:
            # For stopped/completed engagements, use completion time if available
            end_time = getattr(context, 'completed_at', None) or datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
        
        # Ensure minimum 1 second for completed engagements (round up from fractional)
        if duration < 1.0 and context.state not in (EngagementState.RUNNING, EngagementState.PAUSED, EngagementState.INITIALIZING):
            duration = 1.0
        
        # Get operator from config
        config = getattr(context, 'engagement_config', None) or {}
        operator = config.get("engagement", {}).get("operator", "unknown")
        if isinstance(operator, dict):
            operator = operator.get("username", "unknown")
        
        return EngagementStatistics(
            engagement_id=engagement_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat() if end_time else None,
            duration_seconds=int(duration),
            **agents,
            **findings,
            **tools,
            **llm,
            **emergence,
            engagement_state=str(context.state),
            operator=operator,
        )
    
    async def _get_finding_stats(self, engagement_id: str) -> dict[str, int]:
        """Get finding statistics.
        
        Args:
            engagement_id: Engagement ID.
            
        Returns:
            Dictionary with finding counts by severity.
        """
        try:
            # Try to get from checkpoint if available
            checkpoint = await self.checkpoint_manager.load(engagement_id)
            if checkpoint and "findings" in checkpoint:
                findings = checkpoint["findings"]
                
                # Count by severity
                critical = sum(1 for f in findings if f.get("severity") == "critical")
                high = sum(1 for f in findings if f.get("severity") == "high")
                medium = sum(1 for f in findings if f.get("severity") == "medium")
                low = sum(1 for f in findings if f.get("severity") == "low")
                
                return {
                    "findings_critical": critical,
                    "findings_high": high,
                    "findings_medium": medium,
                    "findings_low": low,
                    "total_findings": len(findings),
                }
        except Exception as e:
            self._log.warning("finding_stats_failed", error=str(e), engagement_id=engagement_id)
        
        # Default: no findings
        return {
            "findings_critical": 0,
            "findings_high": 0,
            "findings_medium": 0,
            "findings_low": 0,
            "total_findings": 0,
        }
    
    async def _get_agent_stats(self, engagement_id: str, context: Any) -> dict[str, int]:
        """Get agent statistics.
        
        Args:
            engagement_id: Engagement ID.
            context: Engagement context.
            
        Returns:
            Dictionary with agent counts.
        """
        # Default values
        total_spawned = 0
        active = 0
        idle = 0
        error = 0
        max_concurrent = 0
        
        try:
            # Try to get from orchestrator if available
            if hasattr(context, 'orchestrator') and context.orchestrator:
                orchestrator = context.orchestrator
                
                # Get agent counts from router if available
                if hasattr(orchestrator, '_router') and orchestrator._router:
                    router = orchestrator._router
                    
                    # Count agents by state
                    if hasattr(router, 'agents'):
                        agents = router.agents
                        total_spawned = len(agents)
                        
                        # Simple heuristic: assume agents are active if orchestrator is running
                        if context.state == EngagementState.RUNNING:
                            active = len(agents)
                        else:
                            idle = len(agents)
                        
                        max_concurrent = total_spawned
        except Exception as e:
            self._log.warning("agent_stats_failed", error=str(e), engagement_id=engagement_id)
        
        return {
            "total_agents_spawned": total_spawned,
            "active_agents": active,
            "idle_agents": idle,
            "error_agents": error,
            "max_concurrent_agents": max_concurrent,
        }
    
    async def _get_tool_stats(self, engagement_id: str) -> dict[str, int]:
        """Get tool execution statistics.
        
        Args:
            engagement_id: Engagement ID.
            
        Returns:
            Dictionary with tool execution counts.
        """
        try:
            # Try to get tool stats from checkpoint or orchestrator
            context = self.session_manager.get_engagement(engagement_id)
            if context and context.orchestrator:
                orchestrator = context.orchestrator
                
                # Get tool execution count from tool orchestrator if available
                if hasattr(orchestrator, 'tool_orchestrator'):
                    tool_orch = orchestrator.tool_orchestrator
                    
                    # Count from job history if available
                    executed = 0
                    successful = 0
                    failed = 0
                    
                    if hasattr(tool_orch, '_execution_count'):
                        executed = tool_orch._execution_count
                    if hasattr(tool_orch, '_success_count'):
                        successful = tool_orch._success_count
                    if hasattr(tool_orch, '_failure_count'):
                        failed = tool_orch._failure_count
                    
                    if executed > 0:
                        return {
                            "tools_executed": executed,
                            "successful_tools": successful,
                            "failed_tools": failed,
                        }
        except Exception as e:
            self._log.warning("tool_stats_failed", error=str(e), engagement_id=engagement_id)
        
        # Default values if metrics not available
        return {
            "tools_executed": 0,
            "successful_tools": 0,
            "failed_tools": 0,
        }
    
    async def _get_llm_stats(self, engagement_id: str) -> dict[str, int]:
        """Get LLM usage statistics.
        
        Args:
            engagement_id: Engagement ID.
            
        Returns:
            Dictionary with LLM call counts and token usage.
        """
        try:
            # Get metrics from LLM gateway if available
            if self.llm_gateway and hasattr(self.llm_gateway, 'get_engagement_stats'):
                stats = self.llm_gateway.get_engagement_stats(engagement_id)
                return {
                    "llm_calls": stats.get("total_calls", 0),
                    "llm_tokens_input": stats.get("total_input_tokens", 0),
                    "llm_tokens_output": stats.get("total_output_tokens", 0),
                }
        except Exception as e:
            self._log.warning("llm_stats_failed", error=str(e), engagement_id=engagement_id)
        
        # Default values
        return {
            "llm_calls": 0,
            "llm_tokens_input": 0,
            "llm_tokens_output": 0,
        }
    
    async def _get_emergence_stats(self, engagement_id: str) -> dict[str, Any]:
        """Get emergence statistics and coverage.
        
        Args:
            engagement_id: Engagement ID.
            
        Returns:
            Dictionary with emergence score, threshold status, and coverage.
        """
        emergence_score = None
        threshold_met = False
        coverage_percent = 0.0
        
        try:
            # Try to get emergence score from orchestrator
            context = self.session_manager.get_engagement(engagement_id)
            if context and context.orchestrator:
                orchestrator = context.orchestrator
                
                # Get emergence metrics if available
                if hasattr(orchestrator, '_emergence_metrics'):
                    metrics = orchestrator._emergence_metrics
                    if metrics and hasattr(metrics, 'emergence_score'):
                        emergence_score = metrics.emergence_score
                        threshold_met = emergence_score >= 0.20  # NFR35: 20% threshold
                
                # Get coverage from scope validator if available
                if hasattr(orchestrator, '_scope_validator'):
                    validator = orchestrator._scope_validator
                    if validator and hasattr(validator, 'get_coverage_percent'):
                        coverage_percent = validator.get_coverage_percent()
                    elif validator and hasattr(validator, 'coverage_percentage'):
                        coverage_percent = validator.coverage_percentage
        except Exception as e:
            self._log.warning("emergence_stats_failed", error=str(e), engagement_id=engagement_id)
        
        return {
            "emergence_score": emergence_score,
            "emergence_threshold_met": threshold_met,
            "coverage_percent": coverage_percent,
        }
