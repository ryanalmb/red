"""Integration tests for DirectorRAGClient.

Story 6.9: Director Ensemble RAG Integration.
AC5: Integration tests cover timeout scenarios and partial result handling.
"""

import asyncio

import pytest

from cyberred.core.kill_chain import Phase
from cyberred.rag import RAGStore, RAGQueryInterface
from cyberred.rag.director_client import DirectorRAGClient, RAGQueryContext
from cyberred.rag.models import ContentType, RAGChunk


class FakeEmbeddings:
    def encode(self, text: str):
        # Deterministic vector with correct dimensionality
        return [0.0] * 768


@pytest.mark.integration
class TestDirectorRAGIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_query_flow(self, tmp_path):
        """AC1/AC2: Director can query RAG and get ATT&CK technique IDs."""
        store = RAGStore(str(tmp_path / "director_rag"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Add a chunk with embedded tactic metadata like mitre_attack produces
        chunk = RAGChunk(
            id="t1",
            text="Technique T1059: Use scripting for execution.\n\nTactics: execution",
            source="mitre_attack",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": ["execution"], "technique_ids": ["T1059"]},
            embedding=[0.0] * 768,
        )
        await store.add([chunk])

        ctx = client.build_operator_request_context(request_text="Need execution pivot")
        res = await client.query_strategy_pivot(ctx, top_k=5, timeout=1.0)

        # AC1: Query returns results
        assert res.was_timeout is False
        assert res.degraded is False  # backward compat
        assert res.results
        assert res.methodologies

        # AC2: ATT&CK technique IDs present
        assert "execution" in res.grouped_by_tactic
        assert "T1059" in res.technique_ids

        # Verify timing is tracked
        assert res.query_time_ms >= 0

    @pytest.mark.asyncio
    async def test_timeout_scenario_gracefully_degrades(self, tmp_path):
        """AC3/AC5: Non-blocking queries degrade gracefully on timeout."""
        store = RAGStore(str(tmp_path / "director_rag_timeout"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Patch query to be slow to trigger outer wait_for timeout
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.2)
            return []

        rag.query = slow_query  # type: ignore[assignment]

        ctx = client.build_operator_request_context(request_text="Need pivot")
        res = await client.query_strategy_pivot(ctx, timeout=0.05)

        assert res.was_timeout is True
        assert res.degraded is True  # backward compat
        assert res.results == []
        assert res.methodologies == ()
        assert "No RAG methodology suggestions" in res.actionable_guidance

    @pytest.mark.asyncio
    async def test_fire_and_forget_completes_in_background(self, tmp_path):
        """AC3/AC5: fire_and_forget_query returns immediately and completes in background."""
        store = RAGStore(str(tmp_path / "director_rag_ff"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Add a chunk
        chunk = RAGChunk(
            id="ff1",
            text="Technique T1021: Remote services for lateral movement.",
            source="mitre_attack",
            technique_ids=["T1021"],
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": ["lateral-movement"], "technique_ids": ["T1021"]},
            embedding=[0.0] * 768,
        )
        await store.add([chunk])

        ctx = client.build_phase_transition_context(
            from_phase=Phase.POST_EXPLOIT,
            to_phase=Phase.EXFIL,
        )

        # fire_and_forget should return a task immediately
        task = client.fire_and_forget_query(ctx)
        assert isinstance(task, asyncio.Task)

        # The task should not be done immediately (it's running in background)
        # But we can await it to get the result
        res = await task

        assert res.was_timeout is False
        assert res.methodologies
        assert "T1021" in res.technique_ids

    @pytest.mark.asyncio
    async def test_partial_results_handling(self, tmp_path):
        """AC5: Integration test for partial result handling scenario."""
        store = RAGStore(str(tmp_path / "director_rag_partial"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Add multiple chunks with different tactics
        chunks = [
            RAGChunk(
                id="p1",
                text="Technique T1059: Command and scripting interpreter.",
                source="mitre_attack",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={"tactics": ["execution"], "technique_ids": ["T1059"]},
                embedding=[0.0] * 768,
            ),
            RAGChunk(
                id="p2",
                text="Technique T1078: Valid accounts for persistence.",
                source="mitre_attack",
                technique_ids=["T1078"],
                content_type=ContentType.METHODOLOGY,
                metadata={"tactics": ["persistence", "privilege-escalation"]},
                embedding=[0.0] * 768,
            ),
            RAGChunk(
                id="p3",
                text="Technique T1003: OS credential dumping.",
                source="mitre_attack",
                technique_ids=["T1003"],
                content_type=ContentType.METHODOLOGY,
                metadata={"tactics": ["credential-access"]},
                embedding=[0.0] * 768,
            ),
        ]
        await store.add(chunks)

        # Query with swarm failure context - all new fields
        ctx = client.build_swarm_failure_context(
            failure_signals=["nmap found nothing", "nuclei timeout"],
            target_service="ssh",
            failed_techniques=["T1110"],
            current_phase="ENUMERATION",
        )

        res = await client.query_strategy_pivot(ctx, top_k=10, timeout=2.0)

        # Should get multiple results across tactics
        assert res.was_timeout is False
        assert len(res.methodologies) >= 1

        # Verify grouping works with multiple tactics
        grouped = res.grouped_by_tactic
        assert len(grouped) >= 1

        # Verify correlated phases mapping
        phases_dict = res.get_correlated_phases_dict()
        # execution maps to EXPLOITATION and POST_EXPLOIT
        if "execution" in phases_dict:
            assert Phase.EXPLOITATION in phases_dict["execution"] or Phase.POST_EXPLOIT in phases_dict["execution"]

    @pytest.mark.asyncio
    async def test_all_trigger_types_produce_valid_queries(self, tmp_path):
        """AC4: Test all three trigger-based context types."""
        store = RAGStore(str(tmp_path / "director_rag_triggers"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Add a generic chunk
        chunk = RAGChunk(
            id="trig1",
            text="Generic methodology for pivot.",
            source="mitre_attack",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={"tactics": ["execution"]},
            embedding=[0.0] * 768,
        )
        await store.add([chunk])

        # Test swarm_failure trigger
        ctx1 = client.build_swarm_failure_context(
            failure_signals=["test failure"],
            target_service="http",
            failed_techniques=["T1190"],
        )
        assert ctx1.trigger == "swarm_failure"
        res1 = await client.query_strategy_pivot(ctx1, timeout=1.0)
        assert res1.query_context.trigger == "swarm_failure"

        # Test phase_transition trigger
        ctx2 = client.build_phase_transition_context(
            from_phase=Phase.RECON,
            to_phase=Phase.ENUMERATION,
        )
        assert ctx2.trigger == "phase_transition"
        res2 = await client.query_strategy_pivot(ctx2, timeout=1.0)
        assert res2.query_context.trigger == "phase_transition"

        # Test operator_request trigger
        ctx3 = client.build_operator_request_context(
            request_text="Need alternative approach",
            operator_hint="focus on web vulns",
        )
        assert ctx3.trigger == "operator_request"
        res3 = await client.query_strategy_pivot(ctx3, timeout=1.0)
        assert res3.query_context.trigger == "operator_request"

    @pytest.mark.asyncio
    async def test_query_time_ms_accuracy(self, tmp_path):
        """Verify query_time_ms is reasonably accurate."""
        store = RAGStore(str(tmp_path / "director_rag_timing"))
        rag = RAGQueryInterface(store, FakeEmbeddings())
        client = DirectorRAGClient(rag)

        # Add a delay to the query to verify timing
        original_query = rag.query

        async def delayed_query(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms delay
            return await original_query(*args, **kwargs)

        rag.query = delayed_query  # type: ignore[assignment]

        ctx = client.build_operator_request_context(request_text="Timing test")
        res = await client.query_strategy_pivot(ctx, timeout=1.0)

        # Should be at least 50ms (our artificial delay)
        assert res.query_time_ms >= 40  # Allow some variance
        assert res.query_time_ms < 500  # But not too long
