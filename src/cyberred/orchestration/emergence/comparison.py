import asyncio
import time
import uuid
from dataclasses import asdict
from typing import Any

import structlog

from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction, Finding
from cyberred.orchestration.emergence.tracker import DecisionContextTracker
from cyberred.orchestration.emergence.models import (
    AttackPath,
    ComparisonResult,
    EmergenceComparisonConfig,
    PathStep,
    RunResult,
)
from cyberred.orchestration.emergence.metrics import EmergenceMetrics
from cyberred.orchestration.emergence.causal import CausalChainValidator, ChainDepthResult

log = structlog.get_logger().bind(component="emergence_comparison")


class EmergenceComparisonFramework:
    """Framework for comparing isolated vs stigmergic agent runs.
    
    Implements the emergence test protocol per architecture NFR35 requirements.
    Used to validate >20% novel attack chains from stigmergic coordination.
    
    Emergence Score Calculation:
    1. Isolated Run: N agents, no stigmergic pub/sub, record all findings + attack paths
    2. Stigmergic Run: N agents, full pub/sub enabled, record findings + attack paths + decision_context
    3. Emergence Score = len(novel_chains) / len(total_stigmergic_paths)
    4. HARD GATE: Emergence Score > 0.20 (20%)
    """
    
    def __init__(
        self,
        config: EmergenceComparisonConfig,
        event_bus: EventBus,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self._log = log.bind(agent_count=config.agent_count)
        self._metrics = EmergenceMetrics()
    
    async def run_isolated(
        self,
        agents: list[Any],  # List of StigmergicAgent
        targets: list[str],
        scope: dict[str, Any],
    ) -> RunResult:
        """Execute isolated run (no stigmergic coordination)."""
        run_id = str(uuid.uuid4())
        self._log.info("isolated_run_starting", run_id=run_id)
        
        # Disable pub/sub for isolated mode
        self.event_bus.disable_pubsub()
        
        # Create tracker in isolated mode
        tracker = DecisionContextTracker(
            engagement_id=run_id,
            event_bus=self.event_bus,
            isolated_mode=True,
        )
        
        # Configure agents with isolated tracker
        for agent in agents:
            agent._context_tracker = tracker
        
        start_time = time.monotonic()
        
        # Mock execution for agents if they don't have run() method
        # In real integration, we would call agent.run() or start loop
        # For now, we assume agents are executed externally or via mock
        
        # NOTE: Since this framework is usually called by a test runner or orchestrator
        # that manages the agent loop, we mainly setup the environment here.
        # However, to be useful, it needs to capture the output.
        # In a real implementation, this would likely wrap the agent execution loop.
        
        # For the purpose of this story, we assume agents populate their actions/findings lists
        # or we rely on the caller to drive them. But the story implies this method *executes* the run.
        
        # If agents are passed in, we might assume they are ready to run.
        # Let's assume we need to execute them if they have a run method.
        tasks = []
        for agent in agents:
            if hasattr(agent, "run"):
                tasks.append(agent.run(targets, scope))
        
        if tasks:
            await asyncio.gather(*tasks)

        # Collect results from agents
        findings: list[Finding] = []
        actions: list[AgentAction] = []
        
        for agent in agents:
            # Assuming agents expose their collected findings/actions
            # This depends on agent implementation. 
            # If agents publish to bus, we might need to intercept them even if pubsub disabled.
            # But with pubsub disabled, they can't coordinate.
            # We need to collect them directly from agents.
            if hasattr(agent, "findings"):
                findings.extend(agent.findings)
            if hasattr(agent, "actions"):
                actions.extend(agent.actions)
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        # Re-enable pub/sub
        self.event_bus.enable_pubsub()
        
        # Extract attack paths
        attack_paths = self.extract_attack_paths(actions, findings)
        
        self._log.info(
            "isolated_run_complete",
            run_id=run_id,
            findings=len(findings),
            paths=len(attack_paths),
            duration_ms=duration_ms,
        )
        
        return RunResult(
            run_id=run_id,
            mode="isolated",
            agent_count=len(agents),
            findings=[asdict(f) if hasattr(f, "__dataclass_fields__") else (f if isinstance(f, dict) else {"id": str(f)}) for f in findings],
            attack_paths=attack_paths,
            actions=[asdict(a) if hasattr(a, "__dataclass_fields__") else (a if isinstance(a, dict) else {"id": str(a)}) for a in actions],
            duration_ms=duration_ms,
        )
    
    async def run_stigmergic(
        self,
        agents: list[Any],
        targets: list[str],
        scope: dict[str, Any],
    ) -> RunResult:
        """Execute stigmergic run (full pub/sub coordination)."""
        run_id = str(uuid.uuid4())
        self._log.info("stigmergic_run_starting", run_id=run_id)
        
        # Ensure pub/sub is enabled
        self.event_bus.enable_pubsub()
        
        # Create tracker in stigmergic mode
        tracker = DecisionContextTracker(
            engagement_id=run_id,
            event_bus=self.event_bus,
            isolated_mode=False,
        )
        
        # Configure agents with stigmergic tracker
        for agent in agents:
            agent._context_tracker = tracker
        
        start_time = time.monotonic()
        
        # Execute agents
        tasks = []
        for agent in agents:
            if hasattr(agent, "run"):
                tasks.append(agent.run(targets, scope))
        
        if tasks:
            await asyncio.gather(*tasks)
            
        # Collect results
        findings: list[Finding] = []
        actions: list[AgentAction] = []
        
        for agent in agents:
            if hasattr(agent, "findings"):
                findings.extend(agent.findings)
            if hasattr(agent, "actions"):
                actions.extend(agent.actions)
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        # Extract attack paths
        attack_paths = self.extract_attack_paths(actions, findings)
        
        self._log.info(
            "stigmergic_run_complete",
            run_id=run_id,
            findings=len(findings),
            paths=len(attack_paths),
            duration_ms=duration_ms,
        )
        
        return RunResult(
            run_id=run_id,
            mode="stigmergic",
            agent_count=len(agents),
            findings=[asdict(f) if hasattr(f, "__dataclass_fields__") else (f if isinstance(f, dict) else {"id": str(f)}) for f in findings],
            attack_paths=attack_paths,
            actions=[asdict(a) if hasattr(a, "__dataclass_fields__") else (a if isinstance(a, dict) else {"id": str(a)}) for a in actions],
            duration_ms=duration_ms,
        )
    
    def compare(
        self,
        isolated: RunResult,
        stigmergic: RunResult,
    ) -> ComparisonResult:
        """Compare isolated and stigmergic runs to calculate emergence.
        
        Delegates score calculation to EmergenceMetrics for reusability,
        Prometheus integration (OBS11), and detailed statistics.
        """
        self._log.info("comparing_runs", isolated_id=isolated.run_id, stigmergic_id=stigmergic.run_id)
        
        # Delegate score calculation to EmergenceMetrics (Story 7.10)
        emergence_score_result = self._metrics.calculate_emergence_score(isolated, stigmergic)
        
        # Export to Prometheus (OBS11)
        self._metrics.export_prometheus_metrics(
            emergence_score_result,
            engagement_id=stigmergic.run_id,
            run_id=stigmergic.run_id,
        )
        
        # Build shared_paths list (paths not marked as novel)
        shared_paths = [p for p in stigmergic.attack_paths if not p.is_novel]
        
        # Calculate additional metrics (maintain backward compatibility)
        metrics = {
            "isolated_path_count": float(emergence_score_result.total_isolated_paths),
            "stigmergic_path_count": float(emergence_score_result.total_stigmergic_paths),
            "novel_path_count": float(emergence_score_result.novel_path_count),
            "shared_path_count": float(emergence_score_result.shared_path_count),
            "avg_isolated_depth": self._avg_depth(isolated.attack_paths),
            "avg_stigmergic_depth": self._avg_depth(stigmergic.attack_paths),
            "avg_novel_depth": emergence_score_result.avg_novel_depth,
        }
        
        self._log.info(
            "comparison_complete",
            emergence_score=emergence_score_result.score,
            novel_paths=emergence_score_result.novel_path_count,
            hard_gate_passed=emergence_score_result.score > 0.20,
        )
        
        return ComparisonResult(
            isolated_result=isolated,
            stigmergic_result=stigmergic,
            novel_paths=emergence_score_result.novel_paths,
            shared_paths=shared_paths,
            emergence_score=emergence_score_result.score,
            metrics=metrics,
        )
    
    def extract_attack_paths(
        self,
        actions: list[AgentAction],
        findings: list[Finding],
    ) -> list[AttackPath]:
        """Extract attack paths by tracing decision_context chains."""
        # Build lookup maps
        # Handle dict or object
        finding_map: dict[str, Any] = {}
        for f in findings:
            fid = f.get("id") if isinstance(f, dict) else f.id
            if fid:
                finding_map[fid] = f
            
        # Map: Signal ID (Finding ID) -> List of Actions that used this signal
        action_by_signal: dict[str, list[Any]] = {}
        
        for action in actions:
            dc = action.get("decision_context") if isinstance(action, dict) else action.decision_context
            
            if dc:
                for signal_id in dc:
                    if signal_id == "isolated_mode":
                        continue
                    action_by_signal.setdefault(signal_id, []).append(action)
        
        # Find root actions (those with no decision_context or ["isolated_mode"])
        root_actions = []
        for a in actions:
            dc = a.get("decision_context") if isinstance(a, dict) else a.decision_context
            if not dc or dc == ["isolated_mode"]:
                root_actions.append(a)
        
        paths: list[AttackPath] = []
        
        for root_action in root_actions:
            path = self._build_path_from_action(
                root_action, finding_map, action_by_signal, set()
            )
            if path.steps:
                paths.append(path)
        
        return paths
    
    def _build_path_from_action(
        self,
        action: Any,
        finding_map: dict[str, Any],
        action_by_signal: dict[str, list[Any]],
        visited: set[str],
    ) -> AttackPath:
        """Recursively build attack path from action."""
        # Handle dict/object abstraction
        if isinstance(action, dict):
            aid: str = action.get("id", "")
            res_fid: str | None = action.get("result_finding_id")
            target: str = action.get("target", "")
            atype: str = action.get("action_type", "")
            dc: list[str] | None = action.get("decision_context")
        else:
            aid = action.id
            res_fid = action.result_finding_id
            target = action.target
            atype = action.action_type
            dc = action.decision_context

        if aid in visited:
            return AttackPath()
        
        visited.add(aid)
        
        # finding = finding_map.get(res_fid) if res_fid else None
        
        step = PathStep(
            target=target,
            technique=atype,
            finding_id=res_fid or "",
            action_id=aid,
            decision_context=dc or [],
        )
        
        path = AttackPath(steps=[step])
        
        # Follow chain if finding triggered more actions
        if res_fid:
            next_actions = action_by_signal.get(res_fid, [])
            for next_action in next_actions:
                # get ID of next action
                nid = next_action.get("id") if isinstance(next_action, dict) else next_action.id
                
                if nid not in visited:
                    sub_path = self._build_path_from_action(
                        next_action, finding_map, action_by_signal, visited
                    )
                    path.steps.extend(sub_path.steps)
        
        path.depth = len(path.steps)
        return path
    
    def _path_signature(self, path: AttackPath) -> str:
        """Generate signature for path comparison (ignores timing/IDs)."""
        steps_sig = "|".join(
            f"{s.target}:{s.technique}" for s in path.steps
        )
        return steps_sig
    
    def _avg_depth(self, paths: list[AttackPath]) -> float:
        """Calculate average path depth."""
        if not paths:
            return 0.0
        return sum(p.depth for p in paths) / len(paths)
    
    def validate_causal_chains(
        self,
        stigmergic: RunResult,
        engagement_id: str | None = None,
    ) -> ChainDepthResult:
        """Validate causal chain depth meets NFR36 requirement (3+ hops).
        
        This is a HARD GATE: at least one chain must have 3+ hops to pass.
        Integrates with CausalChainValidator and exports Prometheus metrics.
        
        Args:
            stigmergic: RunResult from stigmergic run containing attack_paths.
            engagement_id: Optional engagement ID for metrics labeling.
                          Defaults to stigmergic.run_id if not provided.
        
        Returns:
            ChainDepthResult with validation details.
        
        Raises:
            ValueError: If NFR36 hard gate fails (when used as gate check).
        
        Story 7.11: Causal Chain Depth Validation
        """
        validator = CausalChainValidator()
        
        result = validator.validate_chain_depth(stigmergic.attack_paths)
        
        # Export to Prometheus (OBS12)
        validator.export_prometheus_metrics(
            result,
            engagement_id=engagement_id or stigmergic.run_id,
            run_id=stigmergic.run_id,
        )
        
        self._log.info(
            "causal_chain_validation_complete",
            run_id=stigmergic.run_id,
            passed=result.passed,
            max_depth=result.max_observed_depth,
            chains_meeting_req=result.chains_meeting_requirement,
        )
        
        return result
