"""Director Ensemble RAG Client.

Story 6.9: Director Ensemble RAG Integration.

This module provides a Director-specific adapter over :class:`cyberred.rag.query.RAGQueryInterface`.
Key requirements:
- Non-blocking by default (timeouts degrade gracefully to empty results)
- Output formatted for Director synthesis, grouped by ATT&CK tactic
- Correlate ATT&CK tactics to Cyber-Red kill chain phases
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Literal, Mapping, Optional, Sequence, Set, Tuple

import structlog

from cyberred.core.kill_chain import Phase
from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.models import RAGSearchResult
from cyberred.rag.query import RAGQueryInterface

log = structlog.get_logger()

# Type alias for trigger values
TriggerType = Literal["swarm_failure", "phase_transition", "operator_request"]


@dataclass(frozen=True)
class RAGQueryContext:
    """Structured context for a Director strategy pivot query.
    
    Attributes:
        trigger: The event type that triggered this query.
        summary: Human-readable summary of the query context.
        target_service: Optional target service being attacked (e.g., "ssh", "http").
        failed_techniques: List of ATT&CK technique IDs that have already failed.
        current_phase: Current kill chain phase name.
        environment: Engagement environment metadata.
        operator_hint: Optional hint from operator for query focus.
        failure_signals: List of failure signal descriptions from swarm.
    """

    trigger: TriggerType
    summary: str
    target_service: Optional[str] = None
    failed_techniques: Tuple[str, ...] = field(default_factory=tuple)
    current_phase: Optional[str] = None
    environment: Tuple[Tuple[str, Any], ...] = field(default_factory=tuple)
    operator_hint: Optional[str] = None
    failure_signals: Tuple[str, ...] = field(default_factory=tuple)

    def get_environment_dict(self) -> Dict[str, Any]:
        """Return environment as a mutable dict for convenience."""
        return dict(self.environment)


@dataclass(frozen=True)
class StrategyPivotResult:
    """Director-ready result for a strategy pivot request.
    
    Attributes:
        query_context: The original query context.
        query_text: The generated query text sent to RAG.
        methodologies: List of RAG search results (methodology suggestions).
        techniques_by_tactic: Mapping of ATT&CK tactic to technique IDs.
        correlated_phases: Mapping of tactic to kill chain phases.
        actionable_guidance: Formatted guidance text for Director synthesis.
        query_time_ms: Query execution time in milliseconds.
        was_timeout: Whether the query timed out (graceful degradation).
    """

    query_context: RAGQueryContext
    query_text: str
    methodologies: Tuple[RAGSearchResult, ...] = field(default_factory=tuple)
    techniques_by_tactic: Tuple[Tuple[str, Tuple[str, ...]], ...] = field(default_factory=tuple)
    correlated_phases: Tuple[Tuple[str, Tuple[Phase, ...]], ...] = field(default_factory=tuple)
    actionable_guidance: str = ""
    query_time_ms: int = 0
    was_timeout: bool = False

    def get_techniques_by_tactic_dict(self) -> Dict[str, List[str]]:
        """Return techniques_by_tactic as a mutable dict for convenience."""
        return {k: list(v) for k, v in self.techniques_by_tactic}

    def get_correlated_phases_dict(self) -> Dict[str, List[Phase]]:
        """Return correlated_phases as a mutable dict for convenience."""
        return {k: list(v) for k, v in self.correlated_phases}

    @property
    def results(self) -> List[RAGSearchResult]:
        """Alias for methodologies for backward compatibility."""
        return list(self.methodologies)

    @property
    def technique_ids(self) -> List[str]:
        """Flat list of all technique IDs across all tactics."""
        ids: Set[str] = set()
        for _, techs in self.techniques_by_tactic:
            ids.update(techs)
        return sorted(ids)

    @property
    def grouped_by_tactic(self) -> Dict[str, List[RAGSearchResult]]:
        """Backward compatibility: return methodologies grouped by tactic."""
        grouped: Dict[str, List[RAGSearchResult]] = {}
        for r in self.methodologies:
            tactics = _extract_tactics(r)
            if not tactics:
                grouped.setdefault("unknown", []).append(r)
            else:
                for t in tactics:
                    grouped.setdefault(t, []).append(r)
        return grouped

    @property
    def guidance_text(self) -> str:
        """Alias for actionable_guidance for backward compatibility."""
        return self.actionable_guidance

    @property
    def degraded(self) -> bool:
        """Alias for was_timeout for backward compatibility."""
        return self.was_timeout


def _extract_tactics(result: RAGSearchResult) -> List[str]:
    """Extract tactic names from a RAG search result's metadata."""
    meta = getattr(result, "metadata", {}) or {}
    tactics = meta.get("tactics")
    if isinstance(tactics, str):
        tactics_list = [tactics]
    elif isinstance(tactics, list):
        tactics_list = tactics
    else:
        tactics_list = []
    out: List[str] = []
    for t in tactics_list:
        if not isinstance(t, str):
            continue
        tt = t.strip().lower()
        if tt:
            out.append(tt)
    return out


class DirectorRAGClient:
    """Director-specific adapter for RAG queries.
    
    This client wraps :class:`RAGQueryInterface` with Director-specific behavior:
    - Non-blocking queries with graceful timeout degradation
    - Results grouped by ATT&CK tactic for strategic synthesis
    - Kill chain phase correlation for operational alignment
    
    Example:
        >>> client = DirectorRAGClient(rag_interface)
        >>> ctx = client.build_swarm_failure_context(
        ...     failure_signals=["nuclei found nothing"],
        ...     target_service="ssh",
        ... )
        >>> result = await client.query_strategy_pivot(ctx)
        >>> print(result.actionable_guidance)
    """

    DEFAULT_TIMEOUT_S = 5.0
    DEFAULT_TOP_K = 10

    # Heuristic mapping from ATT&CK tactic to Cyber-Red kill chain phase.
    # This is intentionally coarse: the Director uses it to align methodology
    # suggestions with the current operational phase.
    _TACTIC_TO_PHASE: Mapping[str, Sequence[Phase]] = {
        # MITRE tactic names are typically lower-case with hyphens in STIX
        "reconnaissance": (Phase.RECON,),
        "resource-development": (Phase.RECON,),
        "discovery": (Phase.ENUMERATION,),
        "initial-access": (Phase.EXPLOITATION,),
        "execution": (Phase.EXPLOITATION, Phase.POST_EXPLOIT),
        "persistence": (Phase.POST_EXPLOIT,),
        "privilege-escalation": (Phase.POST_EXPLOIT,),
        "defense-evasion": (Phase.POST_EXPLOIT,),
        "credential-access": (Phase.POST_EXPLOIT,),
        "lateral-movement": (Phase.POST_EXPLOIT,),
        "collection": (Phase.EXFIL,),
        "command-and-control": (Phase.POST_EXPLOIT, Phase.EXFIL),
        "exfiltration": (Phase.EXFIL,),
        "impact": (Phase.EXFIL,),
    }

    def __init__(self, rag: RAGQueryInterface) -> None:
        self._rag = rag

    async def query_strategy_pivot(
        self,
        context: RAGQueryContext,
        *,
        top_k: int = DEFAULT_TOP_K,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> StrategyPivotResult:
        """Query RAG for methodology suggestions for a strategy pivot.

        This method is Director-safe: it will not raise on timeout and will
        instead return an empty result set with was_timeout=True.
        
        Args:
            context: The query context describing the pivot trigger and state.
            top_k: Maximum number of results to return.
            timeout: Query timeout in seconds (default: 5.0 for Director responsiveness).
            
        Returns:
            StrategyPivotResult with methodologies grouped by tactic and timing info.
        """
        start_time_ns = time.perf_counter_ns()

        query_text = self._build_query_text(context)
        results, was_timeout = await self.query_with_fallback(
            query_text,
            top_k=top_k,
            timeout=timeout,
        )

        # Calculate query time
        elapsed_ns = time.perf_counter_ns() - start_time_ns
        query_time_ms = int(elapsed_ns // 1_000_000)

        technique_ids_set = self._extract_technique_ids(results)
        grouped = self._group_by_tactic(results)
        correlated = self._correlate_tactics_to_phases(grouped)
        guidance = self.format_for_director_synthesis(context, grouped)

        # Convert to immutable structures for frozen dataclass
        techniques_by_tactic = tuple(
            (tactic, tuple(sorted(self._get_technique_ids_for_results(res))))
            for tactic, res in sorted(grouped.items())
        )
        correlated_phases = tuple(
            (tactic, tuple(phases))
            for tactic, phases in sorted(correlated.items())
        )

        return StrategyPivotResult(
            query_context=context,
            query_text=query_text,
            methodologies=tuple(results),
            techniques_by_tactic=techniques_by_tactic,
            correlated_phases=correlated_phases,
            actionable_guidance=guidance,
            query_time_ms=query_time_ms,
            was_timeout=was_timeout,
        )

    def _get_technique_ids_for_results(self, results: Sequence[RAGSearchResult]) -> Set[str]:
        """Extract technique IDs from a list of results."""
        return self._extract_technique_ids(results)

    async def query_with_fallback(
        self,
        text: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> tuple[List[RAGSearchResult], bool]:
        """Query RAG with graceful degradation on timeout.

        Returns (results, degraded) where degraded indicates a timeout or other
        non-fatal error.
        """

        try:
            # RAGQueryInterface already enforces its own timeout; we wrap it in
            # an outer wait_for as an additional safety net.
            results = await asyncio.wait_for(
                self._rag.query(text, top_k=top_k, timeout=timeout),
                timeout=timeout,
            )
            return results, False
        except (RAGQueryTimeout, asyncio.TimeoutError) as e:
            log.info("director_rag_timeout", query=text[:80], timeout=timeout, error=str(e))
            return [], True
        except Exception as e:  # defensive: never break Director flow
            log.warning("director_rag_error", query=text[:80], error=str(e))
            return [], True

    def fire_and_forget_query(
        self,
        context: RAGQueryContext,
        *,
        top_k: int = DEFAULT_TOP_K,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> "asyncio.Task[StrategyPivotResult]":
        """Launch a background RAG query.

        Director can continue execution while this runs.
        """

        return asyncio.create_task(self.query_strategy_pivot(context, top_k=top_k, timeout=timeout))

    @staticmethod
    def build_swarm_failure_context(
        *,
        failure_signals: Sequence[str],
        target_service: Optional[str] = None,
        failed_techniques: Optional[Sequence[str]] = None,
        current_phase: Optional[str] = None,
        environment: Optional[Dict[str, Any]] = None,
    ) -> RAGQueryContext:
        """Build query context for repeated swarm failure scenario.
        
        Use this when multiple agent attempts have failed on the same target
        and the Director needs alternative attack methodologies.
        
        Args:
            failure_signals: List of failure descriptions from swarm agents.
            target_service: The service being targeted (e.g., "ssh", "http", "smb").
            failed_techniques: ATT&CK technique IDs that have already been tried.
            current_phase: Current kill chain phase name.
            environment: Additional engagement environment metadata.
            
        Returns:
            RAGQueryContext configured for swarm failure pivot.
        """
        return RAGQueryContext(
            trigger="swarm_failure",
            summary="Repeated agent swarm failures; request methodology pivot guidance.",
            target_service=target_service,
            failed_techniques=tuple(failed_techniques or ()),
            current_phase=current_phase,
            environment=tuple((environment or {}).items()),
            failure_signals=tuple(failure_signals),
        )

    @staticmethod
    def build_phase_transition_context(
        *,
        from_phase: Phase,
        to_phase: Phase,
        target_service: Optional[str] = None,
        environment: Optional[Dict[str, Any]] = None,
    ) -> RAGQueryContext:
        """Build query context for kill chain phase transition.
        
        Use this when transitioning between operational phases to get
        methodology suggestions for the next phase.
        
        Args:
            from_phase: The phase being exited.
            to_phase: The phase being entered.
            target_service: Optional target service context.
            environment: Additional engagement environment metadata.
            
        Returns:
            RAGQueryContext configured for phase transition pivot.
        """
        env_dict = dict(environment or {})
        env_dict["from_phase"] = from_phase.name
        env_dict["to_phase"] = to_phase.name
        return RAGQueryContext(
            trigger="phase_transition",
            summary=f"Transitioning from {from_phase.name} to {to_phase.name}; request next-phase methodology.",
            target_service=target_service,
            current_phase=to_phase.name,
            environment=tuple(env_dict.items()),
            failure_signals=(),
        )

    @staticmethod
    def build_operator_request_context(
        *,
        request_text: str,
        target_service: Optional[str] = None,
        operator_hint: Optional[str] = None,
        current_phase: Optional[str] = None,
        environment: Optional[Dict[str, Any]] = None,
    ) -> RAGQueryContext:
        """Build query context for operator-initiated pivot request.
        
        Use this when the operator manually requests a strategy pivot
        via the TUI or API.
        
        Args:
            request_text: The operator's request description.
            target_service: Optional target service context.
            operator_hint: Optional hint for query focus area.
            current_phase: Current kill chain phase name.
            environment: Additional engagement environment metadata.
            
        Returns:
            RAGQueryContext configured for operator request pivot.
        """
        return RAGQueryContext(
            trigger="operator_request",
            summary=request_text,
            target_service=target_service,
            operator_hint=operator_hint,
            current_phase=current_phase,
            environment=tuple((environment or {}).items()),
            failure_signals=(),
        )

    def format_for_director_synthesis(
        self,
        context: RAGQueryContext,
        grouped_by_tactic: Mapping[str, Sequence[RAGSearchResult]],
    ) -> str:
        """Format grouped results into actionable guidance text.
        
        Args:
            context: The query context for header information.
            grouped_by_tactic: Results grouped by ATT&CK tactic name.
            
        Returns:
            Formatted multi-line string suitable for Director synthesis.
        """
        lines: List[str] = []
        lines.append("Strategy Pivot Guidance (RAG)")
        lines.append(f"Trigger: {context.trigger}")
        lines.append(f"Summary: {context.summary}")

        if context.target_service:
            lines.append(f"Target Service: {context.target_service}")

        if context.current_phase:
            lines.append(f"Current Phase: {context.current_phase}")

        if context.failed_techniques:
            lines.append(f"Failed Techniques: {', '.join(context.failed_techniques[:10])}")

        if context.failure_signals:
            lines.append("Failure Signals:")
            for s in context.failure_signals[:10]:
                lines.append(f"- {s}")

        if context.operator_hint:
            lines.append(f"Operator Hint: {context.operator_hint}")

        if not grouped_by_tactic:
            lines.append("No RAG methodology suggestions available (degraded or empty store).")
            return "\n".join(lines)

        # Prioritize tactics with the most high-scoring items.
        tactics_sorted = sorted(
            grouped_by_tactic.items(),
            key=lambda kv: max((r.score for r in kv[1]), default=0.0),
            reverse=True,
        )

        lines.append("\nRecommendations by ATT&CK tactic:")
        for tactic, results in tactics_sorted:
            if not results:
                continue
            lines.append(f"\n[{tactic}]")
            for r in sorted(results, key=lambda rr: rr.score, reverse=True)[:3]:
                snippet = (r.text or "").strip().replace("\n", " ")
                if len(snippet) > 220:
                    snippet = snippet[:217] + "..."
                techs = ",".join(sorted(set(self._normalize_technique_ids(r.technique_ids))))
                tech_part = f" (Techniques: {techs})" if techs else ""
                lines.append(f"- {snippet}{tech_part} [score={r.score:.3f}]")

        return "\n".join(lines)

    def _build_query_text(self, context: RAGQueryContext) -> str:
        """Build the query text string from context for RAG search."""
        parts = [
            "strategic pivot methodology",
            context.summary,
        ]
        if context.target_service:
            parts.append(f"target_service: {context.target_service}")
        if context.failed_techniques:
            parts.append("failed_techniques: " + "; ".join(context.failed_techniques[:5]))
        if context.failure_signals:
            parts.append("failure_signals: " + "; ".join(context.failure_signals[:5]))
        if context.operator_hint:
            parts.append(f"operator_hint: {context.operator_hint}")
        # Embed limited environment keys to avoid noisy prompts
        if context.environment:
            env_dict = context.get_environment_dict()
            keys = sorted(env_dict.keys())
            preview = {k: env_dict[k] for k in keys[:8]}
            parts.append(f"environment: {preview}")
        return "\n".join(parts)

    def _group_by_tactic(self, results: Sequence[RAGSearchResult]) -> Dict[str, List[RAGSearchResult]]:
        grouped: Dict[str, List[RAGSearchResult]] = {}
        for r in results:
            tactics = self._extract_tactics(r)
            if not tactics:
                grouped.setdefault("unknown", []).append(r)
                continue
            for t in tactics:
                grouped.setdefault(t, []).append(r)
        return grouped

    def _correlate_tactics_to_phases(
        self, grouped_by_tactic: Mapping[str, Sequence[RAGSearchResult]]
    ) -> Dict[str, List[Phase]]:
        correlated: Dict[str, List[Phase]] = {}
        for tactic in grouped_by_tactic.keys():
            phases: List[Phase] = []
            for p in self._TACTIC_TO_PHASE.get(tactic, ()):  # type: ignore[arg-type]
                if p not in phases:
                    phases.append(p)
            correlated[tactic] = phases
        return correlated

    @staticmethod
    def _normalize_technique_ids(ids: Sequence[str]) -> List[str]:
        norm: List[str] = []
        for tid in ids:
            t = (tid or "").strip()
            if not t:
                continue
            norm.append(t)
        return norm

    def _extract_technique_ids(self, results: Sequence[RAGSearchResult]) -> Set[str]:
        technique_ids: Set[str] = set()
        for r in results:
            technique_ids.update(self._normalize_technique_ids(getattr(r, "technique_ids", []) or []))
            meta = getattr(r, "metadata", {}) or {}
            meta_tids = meta.get("technique_ids")
            if isinstance(meta_tids, str):
                technique_ids.add(meta_tids)
            elif isinstance(meta_tids, list):
                technique_ids.update(self._normalize_technique_ids(meta_tids))
        return technique_ids

    @staticmethod
    def _extract_tactics(result: RAGSearchResult) -> List[str]:
        meta = getattr(result, "metadata", {}) or {}
        tactics = meta.get("tactics")
        if isinstance(tactics, str):
            tactics_list = [tactics]
        elif isinstance(tactics, list):
            tactics_list = tactics
        else:
            tactics_list = []
        out: List[str] = []
        for t in tactics_list:
            if not isinstance(t, str):
                continue
            tt = t.strip().lower()
            if tt:
                out.append(tt)
        return out
