import asyncio
import pytest
from enum import Enum
from cyberred.llm.provider import LLMRequest
from cyberred.llm.priority_queue import RequestPriority, PriorityRequest, LLMPriorityQueue
from cyberred.core.exceptions import LLMTimeoutError

class TestRequestPriority:
    def test_request_priority_enum_values(self):
        """Test that RequestPriority has correct values and is IntEnum."""
        assert RequestPriority.DIRECTOR == 0
        assert RequestPriority.AGENT == 1
        assert isinstance(RequestPriority.DIRECTOR, int)
        assert isinstance(RequestPriority.DIRECTOR, Enum)
        
    def test_request_priority_ordering(self):
        """Test that lower value means higher priority (Director < Agent)."""
        assert RequestPriority.DIRECTOR < RequestPriority.AGENT

class TestPriorityRequest:
    @pytest.mark.asyncio
    async def test_priority_request_dataclass(self):
        """Test PriorityRequest fields and comparison."""
        future = asyncio.get_event_loop().create_future()
        request = LLMRequest(prompt="test", model="test")
        
        pr = PriorityRequest(
            request=request,
            priority=RequestPriority.AGENT,
            sequence=1,
            future=future
        )
        
        assert pr.request == request
        assert pr.priority == RequestPriority.AGENT
        assert pr.sequence == 1
        assert pr.future == future

    @pytest.mark.asyncio
    async def test_priority_request_comparison(self):
        """Test comparison logic: Priority first, then sequence (FIFO)."""
        req = LLMRequest(prompt="test", model="test")
        loop = asyncio.get_event_loop()
        f1 = loop.create_future()
        f2 = loop.create_future()
        
        # Case 1: Different priorities
        p_director = PriorityRequest(req, RequestPriority.DIRECTOR, 10, f1)
        p_agent = PriorityRequest(req, RequestPriority.AGENT, 1, f2)
        assert p_director < p_agent
        
        # Case 2: Same priority, different sequence
        p_agent_1 = PriorityRequest(req, RequestPriority.AGENT, 1, f1)
        p_agent_2 = PriorityRequest(req, RequestPriority.AGENT, 2, f2)
        assert p_agent_1 < p_agent_2

class TestLLMPriorityQueue:
    @pytest.mark.asyncio
    async def test_priority_queue_creation(self):
        """Test queue instantiation."""
        queue = LLMPriorityQueue()
        assert isinstance(queue, LLMPriorityQueue)

    @pytest.mark.asyncio
    async def test_enqueue_director_request(self):
        """Test enqueueing a director request."""
        queue = LLMPriorityQueue()
        req = LLMRequest(prompt="director", model="test")
        future = await queue.enqueue_director(req)
        
        assert isinstance(future, asyncio.Future)
        assert not future.done()
        
        # Verify it's in the queue
        dequeued = await queue.dequeue()
        assert dequeued.request == req
        assert dequeued.priority == RequestPriority.DIRECTOR

    @pytest.mark.asyncio
    async def test_enqueue_agent_request(self):
        """Test enqueueing an agent request."""
        queue = LLMPriorityQueue()
        req = LLMRequest(prompt="agent", model="test")
        future = await queue.enqueue_agent(req)
        
        assert isinstance(future, asyncio.Future)
        assert not future.done()
        
        # Verify it's in the queue
        dequeued = await queue.dequeue()
        assert dequeued.request == req
        assert dequeued.priority == RequestPriority.AGENT

    @pytest.mark.asyncio
    async def test_dequeue_returns_highest_priority(self):
        """Test that dequeue respects priority ordering."""
        queue = LLMPriorityQueue()
        req1 = LLMRequest(prompt="agent", model="test")
        req2 = LLMRequest(prompt="director", model="test")
        
        # Enqueue agent first, then director
        await queue.enqueue_agent(req1)
        await queue.enqueue_director(req2)
        
        # Should get director first
        first = await queue.dequeue()
        assert first.priority == RequestPriority.DIRECTOR
        assert first.request == req2
        
        # Then agent
        second = await queue.dequeue()
        assert second.priority == RequestPriority.AGENT
        assert second.request == req1
        
    @pytest.mark.asyncio
    async def test_fifo_within_same_priority(self):
        """Test FIFO ordering within the same priority level."""
        queue = LLMPriorityQueue()
        req1 = LLMRequest(prompt="1", model="test")
        req2 = LLMRequest(prompt="2", model="test")
        req3 = LLMRequest(prompt="3", model="test")
        
        await queue.enqueue_agent(req1)
        await queue.enqueue_agent(req2)
        await queue.enqueue_agent(req3)
        
        assert (await queue.dequeue()).request == req1
        assert (await queue.dequeue()).request == req2
        assert (await queue.dequeue()).request == req3

    @pytest.mark.asyncio
    async def test_mixed_priority_ordering(self):
        """Test complex interleaving of priorities."""
        queue = LLMPriorityQueue()
        
        # Sequence: Agent, Director, Agent, Director
        await queue.enqueue_agent(LLMRequest(prompt="A1", model="test"))
        await queue.enqueue_director(LLMRequest(prompt="D1", model="test"))
        await queue.enqueue_agent(LLMRequest(prompt="A2", model="test"))
        await queue.enqueue_director(LLMRequest(prompt="D2", model="test"))
        
        # Expected: D1, D2, A1, A2
        assert (await queue.dequeue()).request.prompt == "D1"
        assert (await queue.dequeue()).request.prompt == "D2"
        assert (await queue.dequeue()).request.prompt == "A1"
        assert (await queue.dequeue()).request.prompt == "A2"

    @pytest.mark.asyncio
    async def test_queue_metrics(self):
        """Test queue depth and statistics tracking."""
        queue = LLMPriorityQueue()
        
        assert queue.total_queue_depth == 0
        assert queue.director_queue_depth == 0
        assert queue.agent_queue_depth == 0
        
        # Enqueue Director
        await queue.enqueue_director(LLMRequest(prompt="D", model="test"))
        assert queue.director_queue_depth == 1
        assert queue.total_queue_depth == 1
        
        # Enqueue Agent
        await queue.enqueue_agent(LLMRequest(prompt="A", model="test"))
        assert queue.agent_queue_depth == 1
        assert queue.total_queue_depth == 2
        
        # Dequeue Director
        await queue.dequeue()
        assert queue.director_queue_depth == 0
        assert queue.total_queue_depth == 1
        
        # Dequeue Agent
        await queue.dequeue()
        assert queue.agent_queue_depth == 0
        assert queue.total_queue_depth == 0

    @pytest.mark.asyncio
    async def test_queue_statistics_properties(self):
        """Test that implementation exposes statistics properties (Task 8)."""
        queue = LLMPriorityQueue()
        await queue.enqueue_agent(LLMRequest(prompt="A", model="test"))
        await queue.dequeue()
        
        assert queue.total_enqueued == 1
        assert queue.total_dequeued == 1
        assert queue.agent_enqueued == 1
        assert queue.director_enqueued == 0

    @pytest.mark.asyncio
    async def test_result_delivery_success(self):
        """Test successful result delivery via future."""
        queue = LLMPriorityQueue()
        # Mock objects
        req = LLMRequest(prompt="test", model="test")
        from cyberred.llm.provider import LLMResponse, TokenUsage
        resp = LLMResponse(
            content="ok", 
            model="test", 
            usage=TokenUsage(0,0,0), 
            latency_ms=1
        )
        
        # Enqueue and get future
        future = await queue.enqueue_agent(req)
        
        # Simulate processing worker
        priority_request = await queue.dequeue()
        
        # Verify it's the same request
        assert priority_request.request == req
        assert not future.done()
        
        # Complete request - this method doesn't exist yet
        queue.complete_request(priority_request, resp)
        
        # Verify future is done and has result
        assert future.done()
        assert await future == resp

    @pytest.mark.asyncio
    async def test_result_delivery_failure(self):
        """Test failure delivery via future."""
        queue = LLMPriorityQueue()
        req = LLMRequest(prompt="test", model="test")
        future = await queue.enqueue_agent(req)
        
        priority_request = await queue.dequeue()
        
        error = ValueError("Processing failed")
        queue.fail_request(priority_request, error)
        
        assert future.done()
        with pytest.raises(ValueError, match="Processing failed"):
            await future

    @pytest.mark.asyncio
    async def test_queue_context_manager(self):
        """Test async context manager support."""
        queue = LLMPriorityQueue()
        
        # Test basic entry/exit
        async with queue as q:
            assert isinstance(q, LLMPriorityQueue)
            # Should function normally inside context
            await q.enqueue_agent(LLMRequest(prompt="test", model="test"))
            assert q.total_enqueued == 1

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self):
        """Test proper cleanup on shutdown."""
        queue = LLMPriorityQueue()
        
        # Enqueue item
        await queue.enqueue_agent(LLMRequest(prompt="test", model="test"))
        
        # Shutdown (simulated via explicit call or context exit)
        await queue.shutdown()
        
        # Check if queue is logically empty or handle shutdown behavior
        # In this implementation, we mostly ensure no pending tasks block forever
        # For now, just verification that it doesn't crash
        assert True

    @pytest.mark.asyncio
    async def test_dequeue_timeout(self):
        """Test dequeue timeout."""
        queue = LLMPriorityQueue()
        
        with pytest.raises(LLMTimeoutError, match="Dequeue timeout"):
            await queue.dequeue(timeout=0.1)

    @pytest.mark.asyncio
    async def test_result_delivery_idempotency(self):
        """Test that completion/failure on done future is ignored."""
        queue = LLMPriorityQueue()
        req = LLMRequest(prompt="test", model="test")
        future = await queue.enqueue_agent(req)
        
        # Manually cancel future
        future.cancel()
        
        priority_request = await queue.dequeue()
        
        # Try to complete - should be ignored (no exception)
        from cyberred.llm.provider import LLMResponse, TokenUsage
        resp = LLMResponse("ok", "test", TokenUsage(0,0,0), 1)
        queue.complete_request(priority_request, resp)
        
        # Try to fail - should be ignored
        queue.fail_request(priority_request, ValueError("fail"))
        
        assert future.cancelled()
