"""Authorization Queue for Pending Authorization Requests.

Story 10.3: Pending Authorization Queue

Implements a daemon-side queue for pending authorization requests with:
- Thread-safe operations using RLock
- Sorted retrieval (oldest first)
- Serialization for Redis persistence
- 24h timeout detection (FR64)
- No auto-approve/deny policy (FR16)

The queue persists to Redis and syncs with TUI on attach.

Usage:
    from cyberred.daemon.authorization_queue import AuthorizationQueue
    
    queue = AuthorizationQueue()
    queue.add_request(request)
    pending = queue.get_all_pending()  # Sorted oldest first
    
    # Persistence
    data = queue.to_dict()
    restored = AuthorizationQueue.from_dict(data)

FR16: No auto-approve/deny on timeout - requests remain pending.
FR64: System auto-pauses engagement after 24h of pending authorization requests.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cyberred.tui.screens.authorization import AuthorizationRequest

logger = logging.getLogger(__name__)


@dataclass
class AuthorizationQueue:
    """Daemon-side queue for pending authorization requests.
    
    Persists to Redis and syncs with TUI on attach.
    Implements FR16 (no auto-approve/deny) and FR64 (24h auto-pause).
    
    Thread-safe: All operations are protected by an RLock.
    
    Attributes:
        _requests: Dictionary mapping request_id to AuthorizationRequest.
        _lock: Threading lock for thread-safe operations.
    """
    
    _requests: dict[str, "AuthorizationRequest"] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
    
    def add_request(self, request: "AuthorizationRequest") -> None:
        """Add an authorization request to the queue.
        
        If a request with the same ID already exists, it is updated.
        
        Args:
            request: The authorization request to add.
        """
        with self._lock:
            self._requests[request.id] = request
            logger.debug(
                "Added authorization request to queue",
                extra={"request_id": request.id, "target": request.target}
            )
    
    def get_pending_count(self) -> int:
        """Get the number of pending authorization requests.
        
        Thread-safe operation.
        
        Returns:
            Number of requests in the queue.
        """
        with self._lock:
            return len(self._requests)
    
    def get_all_pending(self) -> list["AuthorizationRequest"]:
        """Get all pending authorization requests sorted by timestamp (oldest first).
        
        Thread-safe operation. Returns a copy of the internal data.
        
        Returns:
            List of AuthorizationRequest instances, sorted oldest first.
            Returns a copy, not the internal data structure.
        """
        with self._lock:
            requests = list(self._requests.values())
            # Sort by timestamp (oldest first)
            requests.sort(key=lambda r: r.timestamp)
            return requests
    
    def clear(self) -> int:
        """Remove all pending authorization requests from the queue.
        
        Thread-safe operation. Used for queue management (Story 10.3).
        
        Returns:
            Number of requests that were cleared.
        """
        with self._lock:
            count = len(self._requests)
            self._requests.clear()
            if count > 0:
                logger.debug(
                    "Cleared authorization queue",
                    extra={"cleared_count": count}
                )
            return count
    
    def get_request_by_id(self, request_id: str) -> "AuthorizationRequest | None":
        """Get a specific authorization request by ID.
        
        Args:
            request_id: The unique request identifier.
            
        Returns:
            The AuthorizationRequest if found, None otherwise.
        """
        with self._lock:
            return self._requests.get(request_id)
    
    def remove_request(self, request_id: str) -> bool:
        """Remove an authorization request from the queue.
        
        Args:
            request_id: The unique request identifier.
            
        Returns:
            True if the request was found and removed, False otherwise.
        """
        with self._lock:
            if request_id in self._requests:
                del self._requests[request_id]
                logger.debug(
                    "Removed authorization request from queue",
                    extra={"request_id": request_id}
                )
                return True
            return False
    
    def get_oldest_pending_timestamp(self) -> datetime | None:
        """Get the timestamp of the oldest pending authorization request.
        
        Used for 24h timeout detection (FR64).
        
        Returns:
            The datetime of the oldest request (timezone-aware UTC), 
            or None if queue is empty.
        """
        with self._lock:
            if not self._requests:
                return None
            
            oldest_ts = None
            for request in self._requests.values():
                request_ts = datetime.fromisoformat(request.timestamp)
                # Ensure timezone-aware (assume UTC if naive)
                if request_ts.tzinfo is None:
                    request_ts = request_ts.replace(tzinfo=timezone.utc)
                if oldest_ts is None or request_ts < oldest_ts:
                    oldest_ts = request_ts
            
            return oldest_ts
    
    def check_24h_timeout(self) -> bool:
        """Check if the oldest pending request exceeds 24 hours.
        
        Per FR64: System auto-pauses engagement after 24h of pending
        authorization requests.
        
        Note: This does NOT auto-deny requests (per FR16). It only
        signals that an auto-pause should be triggered.
        
        Thread-safe: Performs the check atomically with the lock held.
        
        Returns:
            True if oldest request is older than 24 hours, False otherwise.
        """
        with self._lock:
            oldest_ts = self._get_oldest_pending_timestamp_unsafe()
            if oldest_ts is None:
                return False
            
            age = datetime.now(timezone.utc) - oldest_ts
            return age >= timedelta(hours=24)
    
    def _get_oldest_pending_timestamp_unsafe(self) -> datetime | None:
        """Get oldest timestamp without acquiring lock (internal use only).
        
        MUST be called with self._lock held.
        
        Returns:
            The datetime of the oldest request (timezone-aware UTC),
            or None if queue is empty.
        """
        if not self._requests:
            return None
        
        oldest_ts = None
        for request in self._requests.values():
            request_ts = datetime.fromisoformat(request.timestamp)
            # Ensure timezone-aware (assume UTC if naive)
            if request_ts.tzinfo is None:
                request_ts = request_ts.replace(tzinfo=timezone.utc)
            if oldest_ts is None or request_ts < oldest_ts:
                oldest_ts = request_ts
        
        return oldest_ts
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize the queue to a dictionary for Redis persistence.
        
        Returns:
            Dictionary representation of the queue.
        """
        with self._lock:
            return {
                "requests": [
                    _request_to_dict(request)
                    for request in self._requests.values()
                ]
            }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorizationQueue":
        """Deserialize a queue from a dictionary.
        
        Args:
            data: Dictionary representation of the queue (must have 'requests' key).
            
        Returns:
            AuthorizationQueue instance.
            
        Raises:
            ValueError: If a request in the data is missing required fields.
        """
        # Import here to avoid circular imports
        from cyberred.tui.screens.authorization import AuthorizationRequest
        
        queue = cls()
        
        requests_data = data.get("requests", [])
        for i, req_data in enumerate(requests_data):
            if not isinstance(req_data, dict):
                raise ValueError(f"Request at index {i} must be a dictionary")
            # Validate required fields before deserialization
            required_fields = ["id", "target", "proposed_action"]
            missing = [f for f in required_fields if f not in req_data]
            if missing:
                raise ValueError(
                    f"Request at index {i} missing required fields: {missing}"
                )
            request = AuthorizationRequest.from_dict(req_data)
            queue.add_request(request)
        
        return queue


def _request_to_dict(request: "AuthorizationRequest") -> dict[str, Any]:
    """Convert an AuthorizationRequest to a dictionary.
    
    Args:
        request: The authorization request.
        
    Returns:
        Dictionary representation.
    """
    # Import here to avoid circular imports
    from cyberred.tui.screens.authorization import SwarmSnapshot
    
    result = {
        "id": request.id,
        "request_type": request.request_type,
        "agent_id": request.agent_id,
        "target": request.target,
        "proposed_action": request.proposed_action,
        "risk_level": request.risk_level,
        "related_findings": request.related_findings,
        "decision_context": request.decision_context,
        "timestamp": request.timestamp,
        "attck_technique": request.attck_technique,
        "attck_tactic": request.attck_tactic,
        "origin_time_ns": request.origin_time_ns,
    }
    
    # Handle swarm_snapshot if present
    if request.swarm_snapshot is not None:
        if isinstance(request.swarm_snapshot, SwarmSnapshot):
            result["swarm_snapshot"] = {
                "timestamp": request.swarm_snapshot.timestamp,
                "total_agents": request.swarm_snapshot.total_agents,
                "by_status": request.swarm_snapshot.by_status,
                "by_target": request.swarm_snapshot.by_target,
            }
        else:
            result["swarm_snapshot"] = request.swarm_snapshot
    else:
        result["swarm_snapshot"] = None
    
    return result
