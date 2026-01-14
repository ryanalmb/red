"""Agent RAG Escalation module for querying alternative attack methodologies."""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import structlog

from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.models import ContentType, RAGSearchResult
from cyberred.rag.query import RAGQueryInterface

log = structlog.get_logger()

# Constants for input validation
MAX_TARGET_SERVICE_LENGTH = 256
MAX_TECHNIQUE_ID_LENGTH = 64
MAX_FAILED_TECHNIQUES = 100


@dataclass(frozen=True, slots=True)
class AgentRAGContext:
    """Context for agent RAG escalation queries.

    Attributes:
        agent_id: Unique identifier for the agent making the request.
        target_service: The service being targeted (e.g., 'ssh', 'http').
        target_hash: Hash identifying the specific target.
        failed_techniques: List of technique IDs that have already failed.
        failure_count: Number of consecutive failures for this target.
        environment: Additional environment context (e.g., OS, version).
        engagement_id: Optional engagement identifier for audit logging.
    """

    agent_id: str
    target_service: str
    target_hash: str
    failed_techniques: tuple[str, ...]  # tuple for frozen dataclass
    failure_count: int
    environment: Dict[str, Any]
    engagement_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class AgentEscalationResult:
    """Result of RAG escalation query.

    Attributes:
        context: The original context used for the query.
        methodologies: List of RAG search results with alternative methodologies.
        selected_technique: The top recommended technique ID, if any.
        query_time_ms: Time taken for the RAG query in milliseconds.
        was_successful: Whether the query returned any results.
        timed_out: Whether the query timed out.
    """

    context: AgentRAGContext
    methodologies: tuple[RAGSearchResult, ...]  # tuple for frozen dataclass
    selected_technique: Optional[str]
    query_time_ms: int
    was_successful: bool
    timed_out: bool = False


class AgentRAGEscalator:
    """Manages RAG-based escalation for agents when techniques fail.

    This class tracks failure counts per target/technique combination and
    triggers RAG queries when the failure threshold is exceeded. It provides
    thread-safe operations for concurrent agent access.

    Attributes:
        ESCALATION_THRESHOLD: Number of failures before triggering escalation.
    """

    ESCALATION_THRESHOLD = 3

    def __init__(self, rag_interface: RAGQueryInterface) -> None:
        """Initialize the escalator with a RAG query interface.

        Args:
            rag_interface: The RAG query interface to use for escalation queries.
        """
        self._rag = rag_interface
        self._failure_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def record_failure(self, target_hash: str, technique_id: str) -> int:
        """Record a technique failure for a target.

        Thread-safe method to increment the failure count for a specific
        target/technique combination.

        Args:
            target_hash: Hash identifying the target.
            technique_id: The technique that failed.

        Returns:
            The updated failure count for this target/technique combination.

        Raises:
            ValueError: If target_hash or technique_id are invalid.
        """
        self._validate_target_hash(target_hash)
        self._validate_technique_id(technique_id)

        async with self._lock:
            key = self._make_key(target_hash, technique_id)
            self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
            return self._failure_counts[key]

    async def record_success(self, target_hash: str, technique_id: str) -> None:
        """Record a technique success, resetting the failure count.

        Thread-safe method to clear the failure count when a technique succeeds.

        Args:
            target_hash: Hash identifying the target.
            technique_id: The technique that succeeded.

        Raises:
            ValueError: If target_hash or technique_id are invalid.
        """
        self._validate_target_hash(target_hash)
        self._validate_technique_id(technique_id)

        async with self._lock:
            key = self._make_key(target_hash, technique_id)
            self._failure_counts.pop(key, None)

    async def should_escalate(self, target_hash: str, technique_id: str) -> bool:
        """Check if escalation should be triggered for a target/technique.

        Thread-safe method to check if the failure count has reached the
        escalation threshold.

        Args:
            target_hash: Hash identifying the target.
            technique_id: The technique to check.

        Returns:
            True if failure count >= ESCALATION_THRESHOLD, False otherwise.

        Raises:
            ValueError: If target_hash or technique_id are invalid.
        """
        self._validate_target_hash(target_hash)
        self._validate_technique_id(technique_id)

        async with self._lock:
            key = self._make_key(target_hash, technique_id)
            count = self._failure_counts.get(key, 0)
            return count >= self.ESCALATION_THRESHOLD

    def _validate_target_hash(self, target_hash: str) -> None:
        """Validate target_hash input.

        Args:
            target_hash: The target hash to validate.

        Raises:
            ValueError: If target_hash is empty or too long.
        """
        if not target_hash or not isinstance(target_hash, str):
            raise ValueError("target_hash must be a non-empty string")
        if len(target_hash) > MAX_TARGET_SERVICE_LENGTH:
            raise ValueError(f"target_hash exceeds maximum length of {MAX_TARGET_SERVICE_LENGTH}")

    def _validate_technique_id(self, technique_id: str) -> None:
        """Validate technique_id input.

        Args:
            technique_id: The technique ID to validate.

        Raises:
            ValueError: If technique_id is empty or too long.
        """
        if not technique_id or not isinstance(technique_id, str):
            raise ValueError("technique_id must be a non-empty string")
        if len(technique_id) > MAX_TECHNIQUE_ID_LENGTH:
            raise ValueError(f"technique_id exceeds maximum length of {MAX_TECHNIQUE_ID_LENGTH}")

    def _validate_context(self, context: AgentRAGContext) -> None:
        """Validate the escalation context.

        Args:
            context: The context to validate.

        Raises:
            ValueError: If any context field is invalid.
        """
        if not context.agent_id or not isinstance(context.agent_id, str):
            raise ValueError("agent_id must be a non-empty string")
        if not context.target_service or not isinstance(context.target_service, str):
            raise ValueError("target_service must be a non-empty string")
        if len(context.target_service) > MAX_TARGET_SERVICE_LENGTH:
            raise ValueError(f"target_service exceeds maximum length of {MAX_TARGET_SERVICE_LENGTH}")
        if not context.target_hash:
            raise ValueError("target_hash must be a non-empty string")
        if len(context.failed_techniques) > MAX_FAILED_TECHNIQUES:
            raise ValueError(f"failed_techniques exceeds maximum count of {MAX_FAILED_TECHNIQUES}")

    def _make_key(self, target_hash: str, technique_id: str) -> str:
        """Create a unique key for tracking failure counts.

        Args:
            target_hash: Hash identifying the target.
            technique_id: The technique identifier.

        Returns:
            A combined key string.
        """
        return f"{target_hash}:{technique_id}"

    def _build_query_string(self, context: AgentRAGContext) -> str:
        """Build the RAG query string from context.

        Args:
            context: The escalation context containing target and failure info.

        Returns:
            A formatted query string for the RAG interface.
        """
        parts = [
            f"alternative attack methodologies for {context.target_service}",
        ]
        if context.failed_techniques:
            failed_list = ", ".join(context.failed_techniques)
            parts.append(f"excluding techniques: {failed_list}")
        if context.environment.get("os"):
            parts.append(f"target OS: {context.environment['os']}")
        return " ".join(parts)

    async def escalate(self, context: AgentRAGContext) -> AgentEscalationResult:
        """Query RAG for alternative attack methodologies.

        Performs a RAG query to find alternative techniques when the current
        approach has failed multiple times. Handles timeouts gracefully.

        Args:
            context: The escalation context with target and failure information.

        Returns:
            AgentEscalationResult containing methodologies and selection.

        Raises:
            ValueError: If context validation fails.
        """
        self._validate_context(context)

        query = self._build_query_string(context)
        start_time = time.monotonic()
        timed_out = False
        results: List[RAGSearchResult] = []

        try:
            results = await self._rag.query(
                text=query,
                top_k=5,
                filter_content_type=ContentType.METHODOLOGY,
            )
        except RAGQueryTimeout:
            timed_out = True
            log.warning(
                "agent_rag_escalation_timeout",
                agent_id=context.agent_id,
                target=context.target_service,
                target_hash=context.target_hash,
                engagement_id=context.engagement_id,
            )

        query_time_ms = int((time.monotonic() - start_time) * 1000)

        log.info(
            "agent_rag_escalation",
            agent_id=context.agent_id,
            target=context.target_service,
            target_hash=context.target_hash,
            failed_techniques=list(context.failed_techniques),
            failure_count=context.failure_count,
            result_count=len(results),
            query_time_ms=query_time_ms,
            engagement_id=context.engagement_id,
            timed_out=timed_out,
            decision_context={
                "trigger": "exploit_failure_threshold",
                "threshold": self.ESCALATION_THRESHOLD,
                "alternative_count": len(results),
            },
        )

        selected_technique = None
        if results and results[0].technique_ids:
            selected_technique = results[0].technique_ids[0]

        return AgentEscalationResult(
            context=context,
            methodologies=tuple(results),
            selected_technique=selected_technique,
            query_time_ms=query_time_ms,
            was_successful=len(results) > 0,
            timed_out=timed_out,
        )
