"""LLM Priority Queue module for Cyber-Red.

This module provides the priority queue implementation for LLM requests.
It ensures Director strategic requests are processed before Agent requests,
preventing starvation during high load.
"""

import asyncio
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse
from cyberred.core.exceptions import LLMTimeoutError

log = structlog.get_logger()


class RequestPriority(IntEnum):
    """Request priority levels for LLM queue.
    
    Lower numeric value = higher priority.
    DIRECTOR (0) always processes before AGENT (1).
    """
    DIRECTOR = 0  # Strategic re-planning, never starved
    AGENT = 1     # Individual agent requests


@dataclass
class PriorityRequest:
    """Wrapper for prioritized LLM request.
    
    Comparison is first by priority, then by sequence (FIFO).
    """
    request: LLMRequest
    priority: RequestPriority
    sequence: int
    future: asyncio.Future
    
    def __lt__(self, other: "PriorityRequest") -> bool:
        """Compare requests for priority queue ordering.
        
        Args:
            other: Another PriorityRequest to compare with.
            
        Returns:
            True if self should be dequeued before other.
        """
        # First by priority (lower = higher priority)
        if self.priority != other.priority:
            return self.priority < other.priority
        # Then by sequence (FIFO within priority)
        return self.sequence < other.sequence


class LLMPriorityQueue:
    """Priority queue for LLM requests.
    
    Director requests (priority 0) always processed before agent requests (priority 1).
    Within same priority, FIFO ordering is maintained.
    
    Per architecture: Prevents agent flash crowd from blocking Director.
    """
    
    def __init__(self, maxsize: int = 0) -> None:
        """Initialize priority queue.
        
        Args:
            maxsize: Maximum size of the queue. 0 = infinite.
        """
        self._queue: asyncio.PriorityQueue[PriorityRequest] = asyncio.PriorityQueue(maxsize)
        self._sequence_counter = 0
        self._lock = threading.Lock()
        
        # Metrics
        self._director_pending = 0
        self._agent_pending = 0
        self._total_enqueued = 0
        self._director_enqueued = 0
        self._agent_enqueued = 0
        self._total_dequeued = 0
    
    def _next_sequence(self) -> int:
        """Get next sequence number (thread-safe)."""
        with self._lock:
            seq = self._sequence_counter
            self._sequence_counter += 1
            return seq
    
    async def enqueue_director(self, request: LLMRequest) -> asyncio.Future:
        """Enqueue a Director request with highest priority.
        
        Args:
            request: The LLM request to enqueue.
            
        Returns:
            Future that will contain the result.
        """
        return await self._enqueue(request, RequestPriority.DIRECTOR)
    
    async def enqueue_agent(self, request: LLMRequest) -> asyncio.Future:
        """Enqueue an Agent request with normal priority.
        
        Args:
            request: The LLM request to enqueue.
            
        Returns:
            Future that will contain the result.
        """
        return await self._enqueue(request, RequestPriority.AGENT)
    
    async def _enqueue(self, request: LLMRequest, priority: RequestPriority) -> asyncio.Future:
        """Internal enqueue helper."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        seq = self._next_sequence()
        
        priority_request = PriorityRequest(
            request=request,
            priority=priority,
            sequence=seq,
            future=future,
        )
        
        await self._queue.put(priority_request)
        
        with self._lock:
            self._total_enqueued += 1
            if priority == RequestPriority.DIRECTOR:
                self._director_enqueued += 1
                self._director_pending += 1
            else:
                self._agent_enqueued += 1
                self._agent_pending += 1
        
        log.info(
            "request_enqueued",
            priority=priority.name,
            sequence=seq,
            queue_depth=self.total_queue_depth,
        )
        
        return future
    
    async def dequeue(self, timeout: Optional[float] = None) -> PriorityRequest:
        """Dequeue next request by priority, FIFO within priority.
        
        Args:
            timeout: Optional timeout in seconds.
            
        Returns:
            The next PriorityRequest.
            
        Raises:
            LLMTimeoutError: If timeout expires.
        """
        if timeout is not None:
            try:
                priority_request = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise LLMTimeoutError(
                    provider="LLMPriorityQueue",
                    timeout_seconds=timeout,
                    message="Dequeue timeout"
                )
        else:
            priority_request = await self._queue.get()
        
        with self._lock:
            self._total_dequeued += 1
            if priority_request.priority == RequestPriority.DIRECTOR:
                self._director_pending -= 1
            else:
                self._agent_pending -= 1
        
        log.info(
            "request_dequeued",
            priority=priority_request.priority.name,
            sequence=priority_request.sequence,
        )
        
        return priority_request
    
    @property
    def director_queue_depth(self) -> int:
        """Return pending Director requests."""
        with self._lock:
            return self._director_pending
    
    @property
    def agent_queue_depth(self) -> int:
        """Return pending Agent requests."""
        with self._lock:
            return self._agent_pending
    
    @property
    def total_queue_depth(self) -> int:
        """Return total pending requests."""
        with self._lock:
            return self._director_pending + self._agent_pending
            
    @property
    def total_enqueued(self) -> int:
        """Return total requests enqueued since init."""
        with self._lock:
            return self._total_enqueued
            
    @property
    def director_enqueued(self) -> int:
        """Return total Director requests enqueued."""
        with self._lock:
            return self._director_enqueued

    @property
    def agent_enqueued(self) -> int:
        """Return total Agent requests enqueued."""
        with self._lock:
            return self._agent_enqueued
            
    @property
    def total_dequeued(self) -> int:
        """Return total requests dequeued since init."""
        with self._lock:
            return self._total_dequeued
            
    def complete_request(self, priority_request: PriorityRequest, response: "LLMResponse") -> None:
        """Complete a request by setting the result on its future.
        
        Args:
            priority_request: The request being completed.
            response: The LLM response to set as result.
        """
        if not priority_request.future.done():
            priority_request.future.set_result(response)
            log.info(
                "request_completed",
                priority=priority_request.priority.name,
                sequence=priority_request.sequence,
            )
            
    def fail_request(self, priority_request: PriorityRequest, exception: Exception) -> None:
        """Fail a request by setting exception on its future.
        
        Args:
            priority_request: The request being failed.
            exception: The exception to set.
        """
        if not priority_request.future.done():
            priority_request.future.set_exception(exception)
            log.error(
                "request_failed",
                priority=priority_request.priority.name,
                sequence=priority_request.sequence,
                error=str(exception),
            )

    async def shutdown(self) -> None:
        """Shutdown the queue and clean up resources.
        
        Currently just logs the shutdown event.
        Future improvements could handle draining or cancelling pending tasks.
        """
        log.info("queue_shutdown", pending_director=self._director_pending, pending_agent=self._agent_pending)
        
    async def __aenter__(self) -> "LLMPriorityQueue":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and shutdown."""
        await self.shutdown()
