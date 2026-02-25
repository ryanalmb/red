"""Unit tests for DirectorRAGClient.

Story 6.9: Director Ensemble RAG Integration.
Tests cover all acceptance criteria and data model behavior.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from cyberred.core.kill_chain import Phase
from cyberred.rag.director_client import DirectorRAGClient, RAGQueryContext, StrategyPivotResult
from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.models import ContentType, RAGSearchResult


@pytest.mark.unit
class TestDirectorRAGClient:
    @pytest.fixture
    def rag(self):
        rag = AsyncMock()
        # Provide a .query coroutine
        rag.query = AsyncMock()
        return rag

    @pytest.fixture
    def client(self, rag):
        return DirectorRAGClient(rag)  # type: ignore[arg-type]

    def _result(self, *, score=0.9, tactics=None, technique_ids=None):
        return RAGSearchResult(
            id="1",
            text="Try a methodology.",
            source="mitre_attack",
            technique_ids=list(technique_ids or ["T1059"]),
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": tactics or ["discovery"]},
            score=score,
        )

    @pytest.mark.asyncio
    async def test_query_strategy_pivot_returns_grouped_results(self, client, rag):
        rag.query.return_value = [self._result(tactics=["discovery"])]
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        res = await client.query_strategy_pivot(ctx, top_k=3, timeout=0.5)

        assert res.was_timeout is False
        assert res.degraded is False  # backward compat alias
        assert res.results  # backward compat alias
        assert res.methodologies
        assert "discovery" in res.grouped_by_tactic
        assert res.get_correlated_phases_dict()["discovery"] == [Phase.ENUMERATION]
        assert "T1059" in res.technique_ids

    @pytest.mark.asyncio
    async def test_query_strategy_pivot_includes_timing(self, client, rag):
        """AC: query_time_ms must be tracked."""
        rag.query.return_value = [self._result()]
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        res = await client.query_strategy_pivot(ctx, top_k=1, timeout=0.5)

        assert res.query_time_ms >= 0
        assert isinstance(res.query_time_ms, int)

    @pytest.mark.asyncio
    async def test_timeout_degrades_gracefully(self, client, rag):
        rag.query.side_effect = RAGQueryTimeout("boom")
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        res = await client.query_strategy_pivot(ctx, timeout=0.01)

        assert res.was_timeout is True
        assert res.degraded is True  # backward compat alias
        assert res.results == []
        assert res.methodologies == ()
        assert res.grouped_by_tactic == {}
        assert "No RAG methodology suggestions" in res.actionable_guidance

    def test_context_builders_swarm_failure(self, client):
        """Test swarm failure context with all new fields."""
        ctx = client.build_swarm_failure_context(
            failure_signals=["nuclei found nothing"],
            target_service="ssh",
            failed_techniques=["T1059", "T1021"],
            current_phase="ENUMERATION",
            environment={"phase": "VULNERABILITY"},
        )
        assert ctx.trigger == "swarm_failure"
        assert ctx.failure_signals == ("nuclei found nothing",)
        assert ctx.target_service == "ssh"
        assert ctx.failed_techniques == ("T1059", "T1021")
        assert ctx.current_phase == "ENUMERATION"
        assert ctx.get_environment_dict()["phase"] == "VULNERABILITY"

    def test_context_builders_phase_transition(self, client):
        """Test phase transition context builder."""
        ctx = client.build_phase_transition_context(
            from_phase=Phase.RECON,
            to_phase=Phase.ENUMERATION,
            target_service="http",
        )
        assert ctx.trigger == "phase_transition"
        assert ctx.current_phase == "ENUMERATION"
        assert ctx.target_service == "http"
        env = ctx.get_environment_dict()
        assert env["from_phase"] == "RECON"
        assert env["to_phase"] == "ENUMERATION"

    def test_context_builders_operator_request(self, client):
        """Test operator request context builder with all new fields."""
        ctx = client.build_operator_request_context(
            request_text="Do something else",
            target_service="smb",
            operator_hint="focus on lateral movement",
            current_phase="POST_EXPLOIT",
        )
        assert ctx.summary == "Do something else"
        assert ctx.trigger == "operator_request"
        assert ctx.target_service == "smb"
        assert ctx.operator_hint == "focus on lateral movement"
        assert ctx.current_phase == "POST_EXPLOIT"

    @pytest.mark.asyncio
    async def test_fire_and_forget_returns_task(self, client, rag):
        rag.query.return_value = [self._result()]
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        task = client.fire_and_forget_query(ctx)
        assert isinstance(task, asyncio.Task)
        res = await task
        assert res.results
        assert res.methodologies

    @pytest.mark.asyncio
    async def test_query_with_fallback_handles_generic_exception(self, client, rag):
        rag.query.side_effect = RuntimeError("boom")
        results, degraded = await client.query_with_fallback("q", timeout=0.01)
        assert results == []
        assert degraded is True

    @pytest.mark.asyncio
    async def test_query_with_fallback_handles_outer_timeout(self, client, rag):
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.05)
            return []

        rag.query.side_effect = slow_query
        results, degraded = await client.query_with_fallback("q", timeout=0.001)
        assert results == []
        assert degraded is True

    @pytest.mark.asyncio
    async def test_config_defaults_applied_for_top_k_and_timeout(self, rag):
        rag.query.return_value = [self._result()]
        client = DirectorRAGClient(
            rag,  # type: ignore[arg-type]
            query_timeout_s=1.23,
            max_results=7,
        )
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        await client.query_strategy_pivot(ctx)

        assert rag.query.await_count == 1
        kwargs = rag.query.await_args.kwargs
        assert kwargs["top_k"] == 7
        assert pytest.approx(kwargs["timeout"], rel=0.05) == 1.23

    @pytest.mark.asyncio
    async def test_deadline_aware_timeout_clamps_budget(self, rag):
        rag.query.return_value = [self._result()]
        client = DirectorRAGClient(
            rag,  # type: ignore[arg-type]
            query_timeout_s=5.0,
            deadline_guard_s=0.05,
        )
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")
        deadline = time.monotonic() + 0.2

        await client.query_strategy_pivot(ctx, deadline_monotonic_s=deadline)

        kwargs = rag.query.await_args.kwargs
        assert 0.05 <= kwargs["timeout"] <= 0.2

    @pytest.mark.asyncio
    async def test_deadline_exhausted_degrades_without_query_call(self, rag):
        client = DirectorRAGClient(rag)  # type: ignore[arg-type]

        results, degraded = await client.query_with_fallback(
            "q",
            deadline_monotonic_s=time.monotonic() - 1.0,
        )
        assert results == []
        assert degraded is True
        assert rag.query.await_count == 0

    @pytest.mark.asyncio
    async def test_timeout_raises_when_fallback_disabled(self, rag):
        rag.query.side_effect = RAGQueryTimeout("boom")
        client = DirectorRAGClient(
            rag,  # type: ignore[arg-type]
            fallback_on_timeout=False,
        )

        with pytest.raises(RAGQueryTimeout):
            await client.query_with_fallback("q", timeout=0.01)

    @pytest.mark.asyncio
    async def test_min_score_filters_low_confidence_results(self, rag):
        rag.query.return_value = [
            self._result(score=0.95, technique_ids=["T1110"]),
            self._result(score=0.1, technique_ids=["T0001"]),
        ]
        client = DirectorRAGClient(
            rag,  # type: ignore[arg-type]
            min_score=0.5,
        )
        ctx = RAGQueryContext(trigger="operator_request", summary="Need pivot")

        res = await client.query_strategy_pivot(ctx)

        assert len(res.methodologies) == 1
        assert res.technique_ids == ["T1110"]

    def test_format_for_director_synthesis_covers_branches(self, client):
        """Test synthesis formatting with all new context fields."""
        long_text = "x" * 500
        r1 = RAGSearchResult(
            id="1",
            text=long_text,
            source="s",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": ["execution"]},
            score=0.9,
        )
        r2 = RAGSearchResult(
            id="2",
            text="short",
            source="s",
            technique_ids=[""],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.1,
        )

        grouped = client._group_by_tactic([r1, r2])
        grouped["empty"] = []

        ctx = RAGQueryContext(
            trigger="swarm_failure",
            summary="Need pivot",
            target_service="ssh",
            failed_techniques=("T1059", "T1021"),
            current_phase="ENUMERATION",
            operator_hint="focus on creds",
            environment=(("a", 1), ("b", 2)),
            failure_signals=("sig1", "sig2"),
        )
        text = client.format_for_director_synthesis(ctx, grouped)
        assert "Failure Signals:" in text
        assert "[execution]" in text
        assert "[unknown]" in text
        assert "Target Service: ssh" in text
        assert "Current Phase: ENUMERATION" in text
        assert "Failed Techniques: T1059, T1021" in text
        assert "Operator Hint: focus on creds" in text

    def test_extract_helpers_cover_type_branches(self, client):
        # tactics as string
        r_str_tactic = self._result(tactics="discovery")
        assert client._extract_tactics(r_str_tactic) == ["discovery"]

        # tactics list with non-string entries
        r_mixed = self._result(tactics=["execution", 123, None])
        assert client._extract_tactics(r_mixed) == ["execution"]

        # meta technique_ids as string
        r_meta_tid_str = self._result(tactics=["execution"], technique_ids=["T1059"])
        r_meta_tid_str.metadata["technique_ids"] = "T9999"
        tids = client._extract_technique_ids([r_meta_tid_str])
        assert "T1059" in tids
        assert "T9999" in tids

        # meta technique_ids as list (with blanks)
        r_meta_tid_list = self._result(tactics=["execution"], technique_ids=[" ", "T0001"])
        r_meta_tid_list.metadata["technique_ids"] = ["T0002", ""]
        tids2 = client._extract_technique_ids([r_meta_tid_list])
        assert "T0001" in tids2
        assert "T0002" in tids2

        # unmapped tactic produces empty phase list
        correlated = client._correlate_tactics_to_phases({"unknown-tactic": [r_meta_tid_list]})
        assert correlated["unknown-tactic"] == []

        # whitespace-only tactic should be ignored (covers `if tt:` false branch)
        r_ws = self._result(tactics=["   "])
        assert client._extract_tactics(r_ws) == []

    @pytest.mark.asyncio
    async def test_build_query_text_includes_all_context_fields(self, client, rag):
        """Test that query text includes all new context fields."""
        rag.query.return_value = [self._result(tactics=["discovery"])]
        ctx = RAGQueryContext(
            trigger="swarm_failure",
            summary="Need pivot",
            target_service="ssh",
            failed_techniques=("T1059",),
            operator_hint="focus on creds",
            environment=(("k1", "v1"),),
            failure_signals=("sig1",),
        )
        res = await client.query_strategy_pivot(ctx, top_k=1, timeout=0.5)
        assert res.query_text
        assert "failure_signals:" in res.query_text
        assert "environment:" in res.query_text
        assert "target_service: ssh" in res.query_text
        assert "failed_techniques:" in res.query_text
        assert "operator_hint:" in res.query_text

    def test_correlate_tactics_to_phases_deduplicates(self, client):
        # Force a duplicate mapping to cover the de-dupe branch.
        client._TACTIC_TO_PHASE = {"execution": (Phase.EXPLOITATION, Phase.EXPLOITATION)}  # type: ignore[attr-defined]
        out = client._correlate_tactics_to_phases({"execution": []})
        assert out["execution"] == [Phase.EXPLOITATION]

    def test_strategy_pivot_result_helper_methods(self):
        """Test StrategyPivotResult convenience methods."""
        ctx = RAGQueryContext(trigger="operator_request", summary="test")
        result = StrategyPivotResult(
            query_context=ctx,
            query_text="test query",
            methodologies=(
                RAGSearchResult(
                    id="1",
                    text="method",
                    source="s",
                    technique_ids=["T1059"],
                    content_type=ContentType.METHODOLOGY,
                    metadata={"tactics": ["execution"]},
                    score=0.9,
                ),
            ),
            techniques_by_tactic=(("execution", ("T1059", "T1021")),),
            correlated_phases=(("execution", (Phase.EXPLOITATION,)),),
            actionable_guidance="Do this",
            query_time_ms=42,
            was_timeout=False,
        )

        # Test get_techniques_by_tactic_dict - returns list preserving tuple order
        tbt = result.get_techniques_by_tactic_dict()
        assert tbt == {"execution": ["T1059", "T1021"]}

        # Test get_correlated_phases_dict
        cpd = result.get_correlated_phases_dict()
        assert cpd == {"execution": [Phase.EXPLOITATION]}

        # Test backward compat aliases
        assert result.results == list(result.methodologies)
        assert result.guidance_text == result.actionable_guidance
        assert result.degraded == result.was_timeout
        assert "T1021" in result.technique_ids
        assert "T1059" in result.technique_ids

    def test_rag_query_context_immutability(self):
        """Test that frozen dataclass with tuples is truly immutable."""
        ctx = RAGQueryContext(
            trigger="swarm_failure",
            summary="test",
            failed_techniques=("T1059",),
            environment=(("key", "value"),),
        )

        # Should raise on direct attribute mutation
        with pytest.raises(AttributeError):
            ctx.trigger = "operator_request"  # type: ignore[misc]

        # Tuples are immutable so this is safe
        assert ctx.failed_techniques == ("T1059",)
        assert ctx.get_environment_dict() == {"key": "value"}
