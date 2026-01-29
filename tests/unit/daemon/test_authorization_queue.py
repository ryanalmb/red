"""Unit tests for AuthorizationQueue.

Story 10.3: Pending Authorization Queue

Tests for AuthorizationQueue class with:
- Queue operations (add, remove, get)
- Sorted retrieval (oldest first)
- Serialization (to_dict, from_dict)
- Thread-safe operations
- 24h timeout detection

TDD RED PHASE: Tests written FIRST, implementation follows.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

# Import will fail until implementation exists - this is TDD RED phase
from cyberred.daemon.authorization_queue import AuthorizationQueue
from cyberred.tui.screens.authorization import AuthorizationRequest


class TestAuthorizationQueueInit:
    """Tests for AuthorizationQueue initialization."""

    def test_init_creates_empty_queue(self) -> None:
        """Queue initializes with zero pending requests."""
        queue = AuthorizationQueue()
        assert queue.get_pending_count() == 0

    def test_init_creates_empty_list(self) -> None:
        """Queue initializes with empty pending list."""
        queue = AuthorizationQueue()
        assert queue.get_all_pending() == []

    def test_init_oldest_timestamp_is_none(self) -> None:
        """Queue initializes with no oldest timestamp."""
        queue = AuthorizationQueue()
        assert queue.get_oldest_pending_timestamp() is None


class TestAuthorizationQueueAddRequest:
    """Tests for adding requests to the queue."""

    def test_add_request_increases_count(self) -> None:
        """Adding a request increases pending count."""
        queue = AuthorizationQueue()
        request = _create_test_request("req-001")
        
        queue.add_request(request)
        
        assert queue.get_pending_count() == 1

    def test_add_multiple_requests(self) -> None:
        """Adding multiple requests tracks all of them."""
        queue = AuthorizationQueue()
        
        queue.add_request(_create_test_request("req-001"))
        queue.add_request(_create_test_request("req-002"))
        queue.add_request(_create_test_request("req-003"))
        
        assert queue.get_pending_count() == 3

    def test_add_duplicate_id_updates_existing(self) -> None:
        """Adding request with existing ID updates rather than duplicates."""
        queue = AuthorizationQueue()
        request1 = _create_test_request("req-001", target="192.168.1.1")
        request2 = _create_test_request("req-001", target="192.168.1.2")
        
        queue.add_request(request1)
        queue.add_request(request2)
        
        # Count should still be 1
        assert queue.get_pending_count() == 1
        # Should have updated target
        retrieved = queue.get_request_by_id("req-001")
        assert retrieved is not None
        assert retrieved.target == "192.168.1.2"


class TestAuthorizationQueueGetAllPending:
    """Tests for retrieving all pending requests sorted by timestamp."""

    def test_get_all_pending_returns_sorted_oldest_first(self) -> None:
        """Pending requests are returned sorted by timestamp (oldest first)."""
        queue = AuthorizationQueue()
        
        # Add in non-chronological order
        now = datetime.now(timezone.utc)
        req_newest = _create_test_request("req-003", timestamp=(now + timedelta(minutes=10)).isoformat())
        req_middle = _create_test_request("req-002", timestamp=(now + timedelta(minutes=5)).isoformat())
        req_oldest = _create_test_request("req-001", timestamp=now.isoformat())
        
        queue.add_request(req_newest)
        queue.add_request(req_middle)
        queue.add_request(req_oldest)
        
        pending = queue.get_all_pending()
        
        assert len(pending) == 3
        assert pending[0].id == "req-001"  # oldest
        assert pending[1].id == "req-002"  # middle
        assert pending[2].id == "req-003"  # newest

    def test_get_all_pending_returns_copy(self) -> None:
        """get_all_pending returns a copy, not the internal list."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        
        pending = queue.get_all_pending()
        pending.clear()
        
        # Original queue unaffected
        assert queue.get_pending_count() == 1


class TestAuthorizationQueueGetRequestById:
    """Tests for retrieving a specific request by ID."""

    def test_get_request_by_id_returns_request(self) -> None:
        """Can retrieve a request by its ID."""
        queue = AuthorizationQueue()
        request = _create_test_request("req-001", target="192.168.1.100")
        queue.add_request(request)
        
        retrieved = queue.get_request_by_id("req-001")
        
        assert retrieved is not None
        assert retrieved.id == "req-001"
        assert retrieved.target == "192.168.1.100"

    def test_get_request_by_id_nonexistent_returns_none(self) -> None:
        """Retrieving nonexistent request returns None."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        
        retrieved = queue.get_request_by_id("nonexistent")
        
        assert retrieved is None

    def test_get_request_by_id_empty_queue_returns_none(self) -> None:
        """Retrieving from empty queue returns None."""
        queue = AuthorizationQueue()
        
        retrieved = queue.get_request_by_id("req-001")
        
        assert retrieved is None


class TestAuthorizationQueueRemoveRequest:
    """Tests for removing requests from the queue."""

    def test_remove_request_decreases_count(self) -> None:
        """Removing a request decreases pending count."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        queue.add_request(_create_test_request("req-002"))
        
        result = queue.remove_request("req-001")
        
        assert result is True
        assert queue.get_pending_count() == 1

    def test_remove_request_returns_false_if_not_found(self) -> None:
        """Removing nonexistent request returns False."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        
        result = queue.remove_request("nonexistent")
        
        assert result is False
        assert queue.get_pending_count() == 1

    def test_remove_request_from_empty_queue(self) -> None:
        """Removing from empty queue returns False."""
        queue = AuthorizationQueue()
        
        result = queue.remove_request("req-001")
        
        assert result is False

    def test_removed_request_not_retrievable(self) -> None:
        """Removed request cannot be retrieved by ID."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        queue.remove_request("req-001")
        
        retrieved = queue.get_request_by_id("req-001")
        
        assert retrieved is None


class TestAuthorizationQueueClear:
    """Tests for clearing the queue."""

    def test_clear_removes_all_requests(self) -> None:
        """clear() removes all pending requests."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        queue.add_request(_create_test_request("req-002"))
        queue.add_request(_create_test_request("req-003"))
        
        cleared_count = queue.clear()
        
        assert cleared_count == 3
        assert queue.get_pending_count() == 0

    def test_clear_empty_queue_returns_zero(self) -> None:
        """clear() on empty queue returns 0."""
        queue = AuthorizationQueue()
        
        cleared_count = queue.clear()
        
        assert cleared_count == 0

    def test_clear_makes_requests_unretrievable(self) -> None:
        """Cleared requests cannot be retrieved by ID."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        queue.clear()
        
        assert queue.get_request_by_id("req-001") is None
        assert queue.get_all_pending() == []


class TestAuthorizationQueueOldestTimestamp:
    """Tests for getting oldest pending timestamp."""

    def test_oldest_timestamp_returns_oldest(self) -> None:
        """Returns timestamp of oldest pending request."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        oldest_ts = now - timedelta(hours=2)
        middle_ts = now - timedelta(hours=1)
        newest_ts = now
        
        queue.add_request(_create_test_request("req-001", timestamp=newest_ts.isoformat()))
        queue.add_request(_create_test_request("req-002", timestamp=oldest_ts.isoformat()))
        queue.add_request(_create_test_request("req-003", timestamp=middle_ts.isoformat()))
        
        oldest = queue.get_oldest_pending_timestamp()
        
        assert oldest is not None
        # Compare with tolerance for microseconds
        assert abs((oldest - oldest_ts).total_seconds()) < 1

    def test_oldest_timestamp_updates_on_remove(self) -> None:
        """Oldest timestamp updates when oldest request is removed."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        oldest_ts = now - timedelta(hours=2)
        middle_ts = now - timedelta(hours=1)
        
        queue.add_request(_create_test_request("req-oldest", timestamp=oldest_ts.isoformat()))
        queue.add_request(_create_test_request("req-middle", timestamp=middle_ts.isoformat()))
        
        # Remove oldest
        queue.remove_request("req-oldest")
        
        oldest = queue.get_oldest_pending_timestamp()
        assert oldest is not None
        assert abs((oldest - middle_ts).total_seconds()) < 1

    def test_oldest_timestamp_none_when_empty(self) -> None:
        """Returns None when queue is empty."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))
        queue.remove_request("req-001")
        
        assert queue.get_oldest_pending_timestamp() is None


class TestAuthorizationQueueSerialization:
    """Tests for queue serialization (to_dict/from_dict)."""

    def test_to_dict_returns_serializable_dict(self) -> None:
        """to_dict returns JSON-serializable dictionary."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001", target="192.168.1.1"))
        queue.add_request(_create_test_request("req-002", target="192.168.1.2"))
        
        data = queue.to_dict()
        
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert json_str is not None
        
        # Should contain requests
        assert "requests" in data
        assert len(data["requests"]) == 2

    def test_from_dict_restores_queue(self) -> None:
        """from_dict restores queue from serialized data."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001", target="192.168.1.1"))
        queue.add_request(_create_test_request("req-002", target="192.168.1.2"))
        
        data = queue.to_dict()
        restored = AuthorizationQueue.from_dict(data)
        
        assert restored.get_pending_count() == 2
        assert restored.get_request_by_id("req-001") is not None
        assert restored.get_request_by_id("req-002") is not None

    def test_serialization_roundtrip_preserves_order(self) -> None:
        """Serialization roundtrip preserves request order."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        queue.add_request(_create_test_request("req-001", timestamp=(now - timedelta(hours=2)).isoformat()))
        queue.add_request(_create_test_request("req-002", timestamp=(now - timedelta(hours=1)).isoformat()))
        queue.add_request(_create_test_request("req-003", timestamp=now.isoformat()))
        
        data = queue.to_dict()
        restored = AuthorizationQueue.from_dict(data)
        
        pending = restored.get_all_pending()
        assert pending[0].id == "req-001"
        assert pending[1].id == "req-002"
        assert pending[2].id == "req-003"

    def test_from_dict_empty_data_creates_empty_queue(self) -> None:
        """from_dict with empty data creates empty queue."""
        restored = AuthorizationQueue.from_dict({})
        
        assert restored.get_pending_count() == 0

    def test_from_dict_with_empty_requests_list(self) -> None:
        """from_dict with empty requests list creates empty queue."""
        restored = AuthorizationQueue.from_dict({"requests": []})
        
        assert restored.get_pending_count() == 0

    def test_from_dict_validates_required_fields(self) -> None:
        """from_dict raises ValueError if required fields are missing."""
        # Missing 'id' field
        data = {"requests": [{"target": "10.0.0.1", "proposed_action": "test"}]}
        
        with pytest.raises(ValueError, match="missing required fields.*id"):
            AuthorizationQueue.from_dict(data)

    def test_from_dict_validates_request_is_dict(self) -> None:
        """from_dict raises ValueError if request is not a dictionary."""
        data = {"requests": ["not a dict"]}
        
        with pytest.raises(ValueError, match="must be a dictionary"):
            AuthorizationQueue.from_dict(data)

    def test_from_dict_multiple_missing_fields(self) -> None:
        """from_dict reports all missing fields."""
        data = {"requests": [{"agent_id": "agent-1"}]}  # Missing id, target, proposed_action
        
        with pytest.raises(ValueError, match="missing required fields"):
            AuthorizationQueue.from_dict(data)

    def test_to_dict_with_swarm_snapshot(self) -> None:
        """to_dict serializes SwarmSnapshot correctly."""
        from cyberred.tui.screens.authorization import SwarmSnapshot
        
        queue = AuthorizationQueue()
        request = _create_test_request("req-001", target="192.168.1.1")
        request.swarm_snapshot = SwarmSnapshot(
            timestamp="2026-01-01T00:00:00+00:00",
            total_agents=50,
            by_status={"active": 30, "idle": 20},
            by_target={"192.168.1.0/24": 50},
        )
        queue.add_request(request)
        
        data = queue.to_dict()
        
        assert len(data["requests"]) == 1
        snap = data["requests"][0]["swarm_snapshot"]
        assert snap["timestamp"] == "2026-01-01T00:00:00+00:00"
        assert snap["total_agents"] == 50
        assert snap["by_status"] == {"active": 30, "idle": 20}
        assert snap["by_target"] == {"192.168.1.0/24": 50}

    def test_to_dict_with_dict_swarm_snapshot(self) -> None:
        """to_dict handles dict swarm_snapshot (non-SwarmSnapshot object)."""
        queue = AuthorizationQueue()
        request = _create_test_request("req-001", target="192.168.1.1")
        # Set swarm_snapshot as a dict instead of SwarmSnapshot instance
        request.swarm_snapshot = {  # type: ignore[assignment]
            "timestamp": "2026-01-01T00:00:00+00:00",
            "total_agents": 25,
        }
        queue.add_request(request)
        
        data = queue.to_dict()
        
        snap = data["requests"][0]["swarm_snapshot"]
        assert snap == {"timestamp": "2026-01-01T00:00:00+00:00", "total_agents": 25}


class TestAuthorizationQueue24hTimeout:
    """Tests for 24h timeout detection (FR64)."""

    def test_check_24h_timeout_false_when_empty(self) -> None:
        """check_24h_timeout returns False for empty queue."""
        queue = AuthorizationQueue()
        
        assert queue.check_24h_timeout() is False

    def test_check_24h_timeout_false_when_recent(self) -> None:
        """check_24h_timeout returns False when oldest is recent."""
        queue = AuthorizationQueue()
        queue.add_request(_create_test_request("req-001"))  # Just created
        
        assert queue.check_24h_timeout() is False

    def test_check_24h_timeout_true_when_exceeded(self) -> None:
        """check_24h_timeout returns True when oldest > 24h."""
        queue = AuthorizationQueue()
        
        # Create request with timestamp > 24h ago
        old_ts = datetime.now(timezone.utc) - timedelta(hours=25)
        queue.add_request(_create_test_request("req-001", timestamp=old_ts.isoformat()))
        
        assert queue.check_24h_timeout() is True

    def test_check_24h_timeout_boundary_23h59m(self) -> None:
        """check_24h_timeout returns False at 23h 59m (just under)."""
        queue = AuthorizationQueue()
        
        # Just under 24 hours
        ts = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59)
        queue.add_request(_create_test_request("req-001", timestamp=ts.isoformat()))
        
        assert queue.check_24h_timeout() is False

    def test_check_24h_timeout_boundary_24h01m(self) -> None:
        """check_24h_timeout returns True at 24h 1m (just over)."""
        queue = AuthorizationQueue()
        
        # Just over 24 hours
        ts = datetime.now(timezone.utc) - timedelta(hours=24, minutes=1)
        queue.add_request(_create_test_request("req-001", timestamp=ts.isoformat()))
        
        assert queue.check_24h_timeout() is True

    def test_check_24h_timeout_with_timezone_naive_timestamp(self) -> None:
        """check_24h_timeout handles timezone-naive timestamps correctly.
        
        Bug fix: Timestamps without timezone info should be assumed UTC.
        """
        queue = AuthorizationQueue()
        
        # Create timezone-naive timestamp (no +00:00 suffix) > 24h ago
        old_ts = datetime.now(timezone.utc) - timedelta(hours=25)
        naive_ts = old_ts.replace(tzinfo=None).isoformat()  # Remove timezone info
        
        queue.add_request(_create_test_request("req-001", timestamp=naive_ts))
        
        # Should still detect timeout (assumes UTC for naive timestamps)
        assert queue.check_24h_timeout() is True

    def test_get_oldest_pending_timestamp_with_timezone_naive(self) -> None:
        """get_oldest_pending_timestamp handles timezone-naive timestamps."""
        queue = AuthorizationQueue()
        
        # Create timezone-naive timestamp
        naive_ts = "2026-01-01T12:00:00"  # No timezone
        queue.add_request(_create_test_request("req-001", timestamp=naive_ts))
        
        oldest = queue.get_oldest_pending_timestamp()
        
        # Should return timezone-aware datetime (assumed UTC)
        assert oldest is not None
        assert oldest.tzinfo is not None


class TestAuthorizationQueueThreadSafety:
    """Tests for thread-safe queue operations."""

    def test_concurrent_add_operations(self) -> None:
        """Multiple threads can add requests safely."""
        queue = AuthorizationQueue()
        num_threads = 10
        requests_per_thread = 100
        
        def add_requests(thread_id: int) -> None:
            for i in range(requests_per_thread):
                queue.add_request(_create_test_request(f"req-{thread_id}-{i}"))
        
        threads = [
            threading.Thread(target=add_requests, args=(i,))
            for i in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert queue.get_pending_count() == num_threads * requests_per_thread

    def test_concurrent_add_and_remove(self) -> None:
        """Concurrent add and remove operations are safe."""
        queue = AuthorizationQueue()
        
        # Pre-populate
        for i in range(100):
            queue.add_request(_create_test_request(f"req-{i}"))
        
        removed_count = 0
        lock = threading.Lock()
        
        def remover() -> None:
            nonlocal removed_count
            for i in range(50):
                if queue.remove_request(f"req-{i}"):
                    with lock:
                        removed_count += 1
        
        def adder() -> None:
            for i in range(100, 200):
                queue.add_request(_create_test_request(f"req-{i}"))
        
        t1 = threading.Thread(target=remover)
        t2 = threading.Thread(target=adder)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Should have: initial 100 - removed 50 + added 100 = 150
        assert queue.get_pending_count() == 150


# Helper function to create test requests
def _create_test_request(
    request_id: str,
    target: str = "192.168.1.1",
    timestamp: str | None = None,
    agent_id: str = "agent-001",
    proposed_action: str = "Test action",
) -> AuthorizationRequest:
    """Create a test AuthorizationRequest.
    
    Args:
        request_id: Unique request ID.
        target: Target IP/hostname.
        timestamp: ISO timestamp (defaults to now).
        agent_id: Requesting agent ID.
        proposed_action: Proposed action description.
        
    Returns:
        AuthorizationRequest instance.
    """
    return AuthorizationRequest(
        id=request_id,
        request_type="lateral_move",
        agent_id=agent_id,
        target=target,
        proposed_action=proposed_action,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
    )
