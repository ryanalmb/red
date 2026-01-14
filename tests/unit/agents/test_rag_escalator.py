"""Unit tests for Agent RAG Escalator."""

import pytest
from unittest.mock import AsyncMock, patch

from cyberred.agents.rag_escalator import (
    AgentRAGEscalator,
    AgentRAGContext,
    AgentEscalationResult,
    MAX_TARGET_SERVICE_LENGTH,
    MAX_TECHNIQUE_ID_LENGTH,
    MAX_FAILED_TECHNIQUES,
)
from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.models import RAGSearchResult, ContentType


@pytest.fixture
def mock_rag_interface():
    return AsyncMock()


@pytest.fixture
def escalator(mock_rag_interface):
    return AgentRAGEscalator(mock_rag_interface)


def make_context(
    agent_id="agent1",
    target_service="ssh",
    target_hash="hash1",
    failed_techniques=("T1000",),
    failure_count=3,
    environment=None,
    engagement_id=None,
):
    """Helper to create test contexts with defaults."""
    return AgentRAGContext(
        agent_id=agent_id,
        target_service=target_service,
        target_hash=target_hash,
        failed_techniques=failed_techniques,
        failure_count=failure_count,
        environment=environment or {"os": "linux"},
        engagement_id=engagement_id,
    )


# =============================================================================
# Failure Tracking Tests (now async)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_increments_count(escalator):
    count = await escalator.record_failure("target1", "tech1")
    assert count == 1
    count = await escalator.record_failure("target1", "tech1")
    assert count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_separate_keys(escalator):
    await escalator.record_failure("target1", "tech1")
    count = await escalator.record_failure("target1", "tech2")
    assert count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_success_resets_count(escalator):
    await escalator.record_failure("target1", "tech1")
    await escalator.record_failure("target1", "tech1")
    await escalator.record_success("target1", "tech1")
    assert escalator._failure_counts.get("target1:tech1") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_should_escalate_threshold(escalator):
    # Default threshold is 3
    assert not await escalator.should_escalate("target1", "tech1")
    await escalator.record_failure("target1", "tech1")
    assert not await escalator.should_escalate("target1", "tech1")
    await escalator.record_failure("target1", "tech1")
    assert not await escalator.should_escalate("target1", "tech1")
    await escalator.record_failure("target1", "tech1")
    assert await escalator.should_escalate("target1", "tech1")


# =============================================================================
# Escalate Method Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_calls_rag(escalator, mock_rag_interface):
    mock_rag_interface.query.return_value = [
        RAGSearchResult(
            id="chunk1",
            text="test content",
            source="test",
            metadata={"source": "test"},
            score=0.9,
            technique_ids=["T1234"],
            content_type=ContentType.METHODOLOGY,
        )
    ]

    context = make_context()

    result = await escalator.escalate(context)

    assert result.was_successful is True
    assert len(result.methodologies) == 1
    assert result.selected_technique == "T1234"
    assert result.timed_out is False
    mock_rag_interface.query.assert_called_once()

    # Check query construction
    call_args = mock_rag_interface.query.call_args
    assert "ssh" in call_args.kwargs["text"]
    assert "T1000" in call_args.kwargs["text"]
    assert "linux" in call_args.kwargs["text"]


@pytest.mark.unit
def test_build_query_string_minimal(escalator):
    """Test query string with minimal context (no failed techniques, no OS)."""
    # Create context directly to avoid make_context defaults
    context = AgentRAGContext(
        agent_id="agent-123",
        target_service="ssh:22",
        target_hash="hash123",
        failed_techniques=(),
        failure_count=3,
        environment={},  # Empty - no OS
        engagement_id="eng-1",
    )
    query = escalator._build_query_string(context)
    assert "excluding techniques" not in query
    assert "target OS" not in query
    assert "alternative attack methodologies for ssh:22" == query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_empty_techniques_in_result(escalator, mock_rag_interface):
    # Setup mock with result having NO technique_ids
    result = RAGSearchResult(
        id="1",
        text="Generic Advice",
        source="manual",
        technique_ids=[],  # Empty
        content_type=ContentType.METHODOLOGY,
        metadata={},
        score=0.9,
    )
    mock_rag_interface.query.return_value = [result]

    context = make_context(
        agent_id="agent-1",
        target_service="http",
        target_hash="abcd",
        failed_techniques=(),
        failure_count=3,
        environment={},
        engagement_id="eng-1",
    )

    res = await escalator.escalate(context)
    assert res.was_successful
    assert res.selected_technique is None
    assert len(res.methodologies) == 1
    assert res.timed_out is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_no_results(escalator, mock_rag_interface):
    """Test escalate returns was_successful=False when no results."""
    mock_rag_interface.query.return_value = []

    context = make_context()
    result = await escalator.escalate(context)

    assert result.was_successful is False
    assert len(result.methodologies) == 0
    assert result.selected_technique is None


# =============================================================================
# RAGQueryTimeout Tests (Issue #1)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_handles_timeout(escalator, mock_rag_interface):
    """Test that RAGQueryTimeout is caught and handled gracefully."""
    mock_rag_interface.query.side_effect = RAGQueryTimeout("Query timed out after 5s")

    context = make_context(engagement_id="eng-timeout-test")

    with patch("cyberred.agents.rag_escalator.log") as mock_log:
        result = await escalator.escalate(context)

    # Should return a result with timed_out=True, not raise
    assert result.timed_out is True
    assert result.was_successful is False
    assert len(result.methodologies) == 0
    assert result.selected_technique is None

    # Verify warning was logged
    mock_log.warning.assert_called_once()
    call_args = mock_log.warning.call_args
    assert call_args[0][0] == "agent_rag_escalation_timeout"


# =============================================================================
# Decision Context Logging Tests (Issue #6)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_logs_decision_context(escalator, mock_rag_interface):
    """Test that decision_context is logged with correct structure."""
    mock_rag_interface.query.return_value = [
        RAGSearchResult(
            id="chunk1",
            text="test",
            source="test",
            metadata={},
            score=0.9,
            technique_ids=["T1234"],
            content_type=ContentType.METHODOLOGY,
        ),
        RAGSearchResult(
            id="chunk2",
            text="test2",
            source="test",
            metadata={},
            score=0.8,
            technique_ids=["T5678"],
            content_type=ContentType.METHODOLOGY,
        ),
    ]

    context = make_context(engagement_id="eng-decision-test")

    with patch("cyberred.agents.rag_escalator.log") as mock_log:
        await escalator.escalate(context)

    # Verify decision_context structure in log.info call
    mock_log.info.assert_called_once()
    call_kwargs = mock_log.info.call_args.kwargs

    assert "decision_context" in call_kwargs
    decision_ctx = call_kwargs["decision_context"]
    assert decision_ctx["trigger"] == "exploit_failure_threshold"
    assert decision_ctx["threshold"] == AgentRAGEscalator.ESCALATION_THRESHOLD
    assert decision_ctx["alternative_count"] == 2


# =============================================================================
# Input Validation Tests (Issue #3)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_validates_empty_target_hash(escalator):
    """Test that empty target_hash raises ValueError."""
    with pytest.raises(ValueError, match="target_hash must be a non-empty string"):
        await escalator.record_failure("", "tech1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_validates_empty_technique_id(escalator):
    """Test that empty technique_id raises ValueError."""
    with pytest.raises(ValueError, match="technique_id must be a non-empty string"):
        await escalator.record_failure("target1", "")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_validates_long_target_hash(escalator):
    """Test that overly long target_hash raises ValueError."""
    long_hash = "x" * (MAX_TARGET_SERVICE_LENGTH + 1)
    with pytest.raises(ValueError, match="target_hash exceeds maximum length"):
        await escalator.record_failure(long_hash, "tech1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_failure_validates_long_technique_id(escalator):
    """Test that overly long technique_id raises ValueError."""
    long_tech = "x" * (MAX_TECHNIQUE_ID_LENGTH + 1)
    with pytest.raises(ValueError, match="technique_id exceeds maximum length"):
        await escalator.record_failure("target1", long_tech)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_validates_empty_agent_id(escalator, mock_rag_interface):
    """Test that empty agent_id in context raises ValueError."""
    context = make_context(agent_id="")
    with pytest.raises(ValueError, match="agent_id must be a non-empty string"):
        await escalator.escalate(context)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_validates_empty_target_service(escalator, mock_rag_interface):
    """Test that empty target_service in context raises ValueError."""
    context = make_context(target_service="")
    with pytest.raises(ValueError, match="target_service must be a non-empty string"):
        await escalator.escalate(context)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_validates_long_target_service(escalator, mock_rag_interface):
    """Test that overly long target_service raises ValueError."""
    long_service = "x" * (MAX_TARGET_SERVICE_LENGTH + 1)
    context = make_context(target_service=long_service)
    with pytest.raises(ValueError, match="target_service exceeds maximum length"):
        await escalator.escalate(context)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_validates_too_many_failed_techniques(escalator, mock_rag_interface):
    """Test that too many failed_techniques raises ValueError."""
    many_techniques = tuple(f"T{i}" for i in range(MAX_FAILED_TECHNIQUES + 1))
    context = make_context(failed_techniques=many_techniques)
    with pytest.raises(ValueError, match="failed_techniques exceeds maximum count"):
        await escalator.escalate(context)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_escalate_validates_empty_target_hash(escalator, mock_rag_interface):
    """Test that empty target_hash in context raises ValueError."""
    context = AgentRAGContext(
        agent_id="agent1",
        target_service="ssh",
        target_hash="",  # Empty
        failed_techniques=(),
        failure_count=3,
        environment={},
    )
    with pytest.raises(ValueError, match="target_hash must be a non-empty string"):
        await escalator.escalate(context)


# =============================================================================
# Thread Safety Tests (Issue #2)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_concurrent_record_failure_is_thread_safe(mock_rag_interface):
    """Test that concurrent record_failure calls are thread-safe."""
    import asyncio

    escalator = AgentRAGEscalator(mock_rag_interface)

    async def increment():
        for _ in range(100):
            await escalator.record_failure("target1", "tech1")

    # Run 10 concurrent tasks, each incrementing 100 times
    await asyncio.gather(*[increment() for _ in range(10)])

    # Should have exactly 1000 increments
    assert escalator._failure_counts.get("target1:tech1") == 1000


# =============================================================================
# Dataclass Tests (Issue #5)
# =============================================================================


@pytest.mark.unit
def test_agent_rag_context_is_frozen():
    """Test that AgentRAGContext is immutable."""
    context = make_context()
    with pytest.raises(AttributeError):
        context.agent_id = "new_id"


@pytest.mark.unit
def test_agent_escalation_result_is_frozen():
    """Test that AgentEscalationResult is immutable."""
    context = make_context()
    result = AgentEscalationResult(
        context=context,
        methodologies=(),
        selected_technique=None,
        query_time_ms=100,
        was_successful=False,
        timed_out=False,
    )
    with pytest.raises(AttributeError):
        result.was_successful = True


# =============================================================================
# Export Tests
# =============================================================================


@pytest.mark.unit
def test_exports():
    """Test that all expected symbols are exported from agents module."""
    from cyberred.agents import AgentRAGEscalator, AgentRAGContext, AgentEscalationResult

    assert AgentRAGEscalator is not None
    assert AgentRAGContext is not None
    assert AgentEscalationResult is not None
