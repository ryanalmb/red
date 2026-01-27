import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction

log = structlog.get_logger().bind(component="decision_context_tracker")

"""Signal type weights for relevance scoring in decision context.

These weights determine the order in which signals appear in the decision_context
when attached to an AgentAction. Higher weights indicate more direct influence
on agent decision-making. Used for NFR37 emergence validation and audit trails.

Weight values:
    - finding (1.0): Direct findings from other agents - highest influence
    - strategy (0.9): Director Ensemble strategies - high influence  
    - intel (0.8): Intelligence enrichment results (CVE, KEV data)
    - rag (0.7): RAG escalation results (HackTricks, LOLBAS, etc.)
    - phase (0.6): Phase transitions (recon → exploit → postex)
    - status (0.3): Agent status updates - low influence

Unknown signal types default to 0.5 weight.
"""
SIGNAL_TYPE_WEIGHTS: dict[str, float] = {
    "finding": 1.0,      # Direct findings from other agents - highest weight
    "strategy": 0.9,     # Director Ensemble strategies - high weight
    "intel": 0.8,        # Intelligence enrichment results
    "rag": 0.7,          # RAG escalation results
    "phase": 0.6,        # Phase transitions
    "status": 0.3,       # Agent status updates - low weight
}

@dataclass
class SignalRecord:
    """Record of a stigmergic signal received by an agent.

    Attributes:
        signal_id: Unique identifier for the signal (Finding.id, strategy.id, etc.)
        signal_type: Type of signal (finding, strategy, intel, rag, phase, status)
        source: Source agent/component ID
        timestamp: When signal was received
        weight: Relevance weight based on signal_type
        channel: Original Redis channel the signal came from
    """
    signal_id: str
    signal_type: str
    source: str
    timestamp: datetime
    weight: float
    channel: str

class DecisionContextTracker:
    """Tracks stigmergic signals that influence agent decisions.

    Implements NFR37 requirement for 100% decision_context population.
    Every agent action must have an audit trail of which signals
    influenced the decision.

    Attributes:
        engagement_id: Current engagement ID.
        event_bus: EventBus for audit stream publishing.
        max_history: Maximum signals to retain per agent.
        isolated_mode: If True, returns ["isolated_mode"] for all contexts.
        _signals: Per-agent signal history.
    """

    def __init__(
        self,
        engagement_id: str,
        event_bus: EventBus,
        max_history: int = 100,
        isolated_mode: bool = False,
    ) -> None:
        self.engagement_id = engagement_id
        self.event_bus = event_bus
        self.max_history = max_history
        self.isolated_mode = isolated_mode
        self._signals: dict[str, list[SignalRecord]] = defaultdict(list)
        self._log = log.bind(engagement_id=engagement_id)

    def record_signal(
        self,
        agent_id: str,
        signal_id: str,
        signal_type: str,
        source: str,
        channel: str = "",
    ) -> None:
        """Record a stigmergic signal received by an agent.

        Args:
            agent_id: Agent that received the signal.
            signal_id: Unique identifier of the signal.
            signal_type: Type of signal (finding, strategy, etc.).
            source: Source agent/component.
            channel: Redis channel signal came from.
        """
        if self.isolated_mode:
            return  # Don't record signals in isolated mode

        weight = SIGNAL_TYPE_WEIGHTS.get(signal_type, 0.5)
        record = SignalRecord(
            signal_id=signal_id,
            signal_type=signal_type,
            source=source,
            timestamp=datetime.now(UTC),
            weight=weight,
            channel=channel,
        )

        signals = self._signals[agent_id]
        signals.append(record)

        # Enforce max history (drop oldest)
        if len(signals) > self.max_history:
            self._signals[agent_id] = signals[-self.max_history:]

        self._log.debug(
            "signal_recorded",
            agent_id=agent_id,
            signal_id=signal_id,
            signal_type=signal_type,
        )

    def get_context(self, agent_id: str) -> list[str]:
        """Get signal IDs that influenced agent's pending action.

        Returns:
            List of signal_ids sorted by weight (highest first).
            Returns ["isolated_mode"] if isolated_mode is True.
        """
        if self.isolated_mode:
            return ["isolated_mode"]

        signals = self._signals.get(agent_id, [])
        # Sort by weight descending, then by timestamp descending
        sorted_signals = sorted(
            signals,
            key=lambda s: (s.weight, s.timestamp),
            reverse=True,
        )
        return [s.signal_id for s in sorted_signals]

    def attach_to_action(
        self,
        agent_id: str,
        action: AgentAction,
    ) -> AgentAction:
        """Attach decision context to an agent action.

        Populates action.decision_context with signal IDs,
        clears the agent's context, and publishes to audit stream.

        Args:
            agent_id: Agent that performed the action.
            action: AgentAction to populate.

        Returns:
            AgentAction with decision_context populated.
        """
        context = self.get_context(agent_id)
        action.decision_context = context

        # Publish to audit stream (with event loop guard)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._publish_audit(agent_id, action.id, context)
            )
        except RuntimeError:
            # No running event loop - schedule via run_coroutine_threadsafe or log warning
            self._log.warning(
                "audit_publish_skipped_no_loop",
                agent_id=agent_id,
                action_id=action.id,
                context_count=len(context),
            )

        # Clear context for next action
        self.clear_context(agent_id)

        self._log.info(
            "context_attached",
            agent_id=agent_id,
            action_id=action.id,
            context_count=len(context),
        )

        return action

    def clear_context(self, agent_id: str) -> None:
        """Clear signal history for an agent."""
        if agent_id in self._signals:
            del self._signals[agent_id]

    def get_all_agents(self) -> list[str]:
        """Get all agent IDs with recorded signals."""
        return list(self._signals.keys())

    def get_signal_count(self, agent_id: str) -> int:
        """Get number of signals recorded for an agent."""
        return len(self._signals.get(agent_id, []))

    async def _publish_audit(
        self,
        agent_id: str,
        action_id: str,
        context_ids: list[str],
    ) -> None:
        """Publish context attachment to audit stream."""
        try:
            await self.event_bus.publish(
                "audit:decision_context",
                {
                    "engagement_id": self.engagement_id,
                    "agent_id": agent_id,
                    "action_id": action_id,
                    "context_ids": context_ids,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            self._log.error("audit_publish_failed", error=str(e))
