"""Integration tests for Agent RAG Escalator.

These tests verify the integration between AgentRAGEscalator and RAGQueryInterface,
testing the full escalation flow with mocked external dependencies (embeddings, store).
"""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from cyberred.agents import AgentRAGEscalator, AgentRAGContext, AgentEscalationResult
from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.models import RAGSearchResult, ContentType


@pytest.fixture
def mock_store():
    """Mock vector store that returns empty results by default."""
    store = AsyncMock()
    store.search.return_value = []
    return store


@pytest.fixture
def mock_embeddings():
    """Mock embeddings model - fast, returns fixed vector."""
    embeddings = AsyncMock()
    embeddings.encode.return_value = [0.1, 0.2, 0.3]
    return embeddings


@pytest.fixture
async def real_rag_interface(mock_store, mock_embeddings):
    """Real RAGQueryInterface with mocked external deps (store, embeddings)."""
    from cyberred.rag.query import RAGQueryInterface

    return RAGQueryInterface(store=mock_store, embeddings=mock_embeddings)


@pytest.fixture
def escalator(real_rag_interface):
    """AgentRAGEscalator with real RAGQueryInterface."""
    return AgentRAGEscalator(real_rag_interface)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_escalation_flow(escalator, mock_store, mock_embeddings):
    # Setup mock store to return results
    mock_store.search.return_value = [
        RAGSearchResult(
            id="1",
            text="Use SSH brute force",
            source="manual",
            technique_ids=["T1110"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95,
        )
    ]

    # Simulate failures
    target = "ssh:22"
    technique = "T1000"
    target_hash = "hash123"

    # 1. First failure (now async)
    await escalator.record_failure(target_hash, technique)
    assert not await escalator.should_escalate(target_hash, technique)

    # 2. Second failure
    await escalator.record_failure(target_hash, technique)
    assert not await escalator.should_escalate(target_hash, technique)

    # 3. Third failure - Trigger!
    await escalator.record_failure(target_hash, technique)
    assert await escalator.should_escalate(target_hash, technique)

    # 4. Perform escalation (failed_techniques is now tuple)
    context = AgentRAGContext(
        agent_id="agent-01",
        target_service=target,
        target_hash=target_hash,
        failed_techniques=(technique,),
        failure_count=3,
        environment={"os": "linux"},
    )

    result = await escalator.escalate(context)

    # 5. Verify results
    assert result.was_successful
    assert len(result.methodologies) == 1
    assert result.selected_technique == "T1110"
    assert result.timed_out is False

    # Verify interaction with store and embeddings
    mock_store.search.assert_called_once()

    # Verify query string was encoded (this is where the text is)
    mock_embeddings.encode.assert_called_once()
    call_args = mock_embeddings.encode.call_args
    # Verify query string contains key info
    assert "ssh:22" in call_args.kwargs.get("text", call_args.args[0])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_persistence(escalator):
    target_hash = "persistent_target"
    technique = "T666"

    # record_failure is now async
    count = await escalator.record_failure(target_hash, technique)
    assert count == 1

    # Should persist in memory for same instance
    count = await escalator.record_failure(target_hash, technique)
    assert count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_success_clears_failure_count(escalator):
    """Test that record_success clears the failure count."""
    target_hash = "target_success"
    technique = "T999"

    # Record some failures
    await escalator.record_failure(target_hash, technique)
    await escalator.record_failure(target_hash, technique)
    assert not await escalator.should_escalate(target_hash, technique)

    # Record success - should clear
    await escalator.record_success(target_hash, technique)

    # Failure count should be reset
    assert not await escalator.should_escalate(target_hash, technique)

    # One more failure should only be count=1
    count = await escalator.record_failure(target_hash, technique)
    assert count == 1


# =============================================================================
# AC3: Decision Context Logging for Emergence Metrics
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_logs_decision_context(escalator, mock_store):
    """Test that escalation logs decision_context with required fields for emergence metrics.
    
    AC3: agent logs RAG escalation in decision_context, tracked for emergence metrics.
    """
    mock_store.search.return_value = [
        RAGSearchResult(
            id="alt-1",
            text="Alternative methodology",
            source="hacktricks",
            technique_ids=["T1110.001", "T1110.002"],
            content_type=ContentType.METHODOLOGY,
            metadata={"source": "hacktricks"},
            score=0.92,
        ),
        RAGSearchResult(
            id="alt-2",
            text="Second alternative",
            source="atomic-red",
            technique_ids=["T1078"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.85,
        ),
    ]

    context = AgentRAGContext(
        agent_id="ghost-agent-007",
        target_service="ssh:22",
        target_hash="abc123hash",
        failed_techniques=("T1021.004", "T1110"),
        failure_count=3,
        environment={"os": "linux", "version": "Ubuntu 22.04"},
        engagement_id="engagement-2026-001",
    )

    with patch("cyberred.agents.rag_escalator.log") as mock_log:
        result = await escalator.escalate(context)

    # Verify log.info was called with decision_context
    mock_log.info.assert_called_once()
    call_kwargs = mock_log.info.call_args.kwargs

    # Verify all required fields for emergence metrics
    assert call_kwargs["agent_id"] == "ghost-agent-007"
    assert call_kwargs["target"] == "ssh:22"
    assert call_kwargs["target_hash"] == "abc123hash"
    assert call_kwargs["engagement_id"] == "engagement-2026-001"
    assert call_kwargs["failure_count"] == 3
    assert call_kwargs["result_count"] == 2
    assert "query_time_ms" in call_kwargs

    # Verify decision_context structure (critical for emergence tracking)
    decision_ctx = call_kwargs["decision_context"]
    assert decision_ctx["trigger"] == "exploit_failure_threshold"
    assert decision_ctx["threshold"] == 3
    assert decision_ctx["alternative_count"] == 2


# =============================================================================
# Timeout Integration Test
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_timeout_with_real_interface(mock_embeddings):
    """Test timeout behavior through real RAGQueryInterface.
    
    Simulates a slow store that exceeds timeout, verifying graceful degradation.
    """
    from cyberred.rag.query import RAGQueryInterface

    # Create a slow store that simulates timeout
    slow_store = AsyncMock()

    async def slow_search(*args, **kwargs):
        await asyncio.sleep(0.1)  # Small delay to simulate work
        raise RAGQueryTimeout("Query timed out after 5s")

    slow_store.search.side_effect = slow_search

    # Create interface with slow store
    rag_interface = RAGQueryInterface(store=slow_store, embeddings=mock_embeddings)
    escalator = AgentRAGEscalator(rag_interface)

    context = AgentRAGContext(
        agent_id="timeout-test-agent",
        target_service="rdp:3389",
        target_hash="timeout-target",
        failed_techniques=("T1021.001",),
        failure_count=3,
        environment={"os": "windows"},
    )

    # Should NOT raise - should handle gracefully
    result = await escalator.escalate(context)

    assert result.timed_out is True
    assert result.was_successful is False
    assert len(result.methodologies) == 0
    assert result.selected_technique is None


# =============================================================================
# Query Context Verification
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_query_contains_full_context(escalator, mock_store, mock_embeddings):
    """Test that RAG query includes all context fields (AC2).
    
    AC2: Query context includes: target service, failed techniques, environment.
    """
    mock_store.search.return_value = []

    context = AgentRAGContext(
        agent_id="context-test-agent",
        target_service="smb:445",
        target_hash="context-target",
        failed_techniques=("T1021.002", "T1187", "T1557"),
        failure_count=5,
        environment={"os": "windows", "domain": "corp.local"},
    )

    await escalator.escalate(context)

    # Verify embeddings.encode received the full query
    mock_embeddings.encode.assert_called_once()
    call_args = mock_embeddings.encode.call_args
    query_text = call_args.kwargs.get("text", call_args.args[0])

    # AC2: Query must include target service
    assert "smb:445" in query_text

    # AC2: Query must include failed techniques
    assert "T1021.002" in query_text
    assert "T1187" in query_text
    assert "T1557" in query_text

    # AC2: Query must include environment (OS)
    assert "windows" in query_text


# =============================================================================
# Concurrent Escalations (Thread Safety)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_escalations(mock_store, mock_embeddings):
    """Test multiple agents escalating simultaneously.
    
    Verifies thread safety of failure counting under concurrent load.
    """
    from cyberred.rag.query import RAGQueryInterface

    mock_store.search.return_value = [
        RAGSearchResult(
            id="concurrent-result",
            text="Concurrent test result",
            source="test",
            technique_ids=["T9999"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.9,
        )
    ]

    rag_interface = RAGQueryInterface(store=mock_store, embeddings=mock_embeddings)
    escalator = AgentRAGEscalator(rag_interface)

    # Simulate 5 different agents recording failures concurrently
    async def agent_workflow(agent_num: int):
        target_hash = f"target-{agent_num}"
        technique = f"T{1000 + agent_num}"

        # Record 3 failures to trigger escalation
        for _ in range(3):
            await escalator.record_failure(target_hash, technique)

        # Should now be able to escalate
        assert await escalator.should_escalate(target_hash, technique)

        context = AgentRAGContext(
            agent_id=f"agent-{agent_num:03d}",
            target_service=f"service-{agent_num}",
            target_hash=target_hash,
            failed_techniques=(technique,),
            failure_count=3,
            environment={"agent": agent_num},
        )

        result = await escalator.escalate(context)
        assert result.was_successful
        return result

    # Run 10 agents concurrently
    results = await asyncio.gather(*[agent_workflow(i) for i in range(10)])

    # All should succeed
    assert len(results) == 10
    assert all(r.was_successful for r in results)

    # Verify each agent's failure count is isolated
    for i in range(10):
        target_hash = f"target-{i}"
        technique = f"T{1000 + i}"
        # Should still show as escalation-worthy (count >= 3)
        assert await escalator.should_escalate(target_hash, technique)


# =============================================================================
# Latency Performance Test
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_latency(escalator, mock_store, mock_embeddings):
    """Test that escalation completes within performance budget.
    
    Story requirement: RAG queries should complete quickly for agent responsiveness.
    Target: <500ms with mocked dependencies (real latency depends on embedding model).
    """
    mock_store.search.return_value = [
        RAGSearchResult(
            id="perf-result",
            text="Performance test result",
            source="test",
            technique_ids=["T1234"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95,
        )
    ]

    context = AgentRAGContext(
        agent_id="perf-test-agent",
        target_service="http:80",
        target_hash="perf-target",
        failed_techniques=("T1190", "T1210"),
        failure_count=3,
        environment={"os": "linux", "web_server": "nginx"},
    )

    # Measure actual wall-clock time
    start = time.perf_counter()
    result = await escalator.escalate(context)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # With mocked deps, should be very fast
    assert elapsed_ms < 500, f"Escalation took {elapsed_ms:.2f}ms, expected <500ms"

    # Also verify result.query_time_ms is populated
    assert result.query_time_ms >= 0
    assert result.was_successful


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_latency_multiple_iterations(escalator, mock_store, mock_embeddings):
    """Test latency consistency across multiple escalations."""
    mock_store.search.return_value = [
        RAGSearchResult(
            id="iter-result",
            text="Iteration test",
            source="test",
            technique_ids=["T5555"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.9,
        )
    ]

    latencies = []

    for i in range(20):
        context = AgentRAGContext(
            agent_id=f"iter-agent-{i}",
            target_service="ftp:21",
            target_hash=f"iter-target-{i}",
            failed_techniques=("T1021.002",),
            failure_count=3,
            environment={"iteration": i},
        )

        start = time.perf_counter()
        result = await escalator.escalate(context)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        assert result.was_successful

    # Calculate stats
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    # All iterations should be fast with mocked deps
    assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms too high"
    assert max_latency < 500, f"Max latency {max_latency:.2f}ms exceeds budget"
