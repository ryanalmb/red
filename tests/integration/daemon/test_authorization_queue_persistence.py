"""Integration tests for AuthorizationQueue persistence.

Story 10.3: Pending Authorization Queue

Tests for queue persistence and TUI sync:
- Queue serialization is Redis-compatible (JSON roundtrip)
- Queue state syncs to TUI on attach
- Queue survives TUI detach/reattach cycle
- 24h auto-pause integration

These are integration tests that test ACTUAL PRODUCTION CODE
using JSON roundtrip to simulate Redis storage without requiring
a live Redis instance.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from cyberred.daemon.authorization_queue import AuthorizationQueue
from cyberred.tui.screens.authorization import AuthorizationRequest


class TestAuthorizationQueuePersistence:
    """Integration tests for queue persistence to Redis."""

    def test_queue_to_dict_produces_redis_compatible_json(self) -> None:
        """Verify queue serialization produces valid JSON for Redis storage."""
        queue = AuthorizationQueue()
        
        # Add multiple requests
        for i in range(3):
            queue.add_request(_create_request(f"req-{i}", f"192.168.1.{i}"))
        
        data = queue.to_dict()
        
        # Must be JSON serializable (Redis stores as JSON string)
        json_str = json.dumps(data)
        assert json_str is not None
        
        # Must be deserializable
        parsed = json.loads(json_str)
        assert "requests" in parsed
        assert len(parsed["requests"]) == 3

    def test_queue_roundtrip_through_json(self) -> None:
        """Verify queue survives JSON roundtrip (simulating Redis storage)."""
        original = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        original.add_request(_create_request("req-old", "10.0.0.1", (now - timedelta(hours=2)).isoformat()))
        original.add_request(_create_request("req-new", "10.0.0.2", now.isoformat()))
        
        # Simulate Redis storage: serialize -> deserialize
        json_str = json.dumps(original.to_dict())
        data = json.loads(json_str)
        restored = AuthorizationQueue.from_dict(data)
        
        # Verify state is identical
        assert restored.get_pending_count() == 2
        assert restored.get_request_by_id("req-old") is not None
        assert restored.get_request_by_id("req-new") is not None
        
        # Verify order is preserved (oldest first)
        pending = restored.get_all_pending()
        assert pending[0].id == "req-old"
        assert pending[1].id == "req-new"

    def test_queue_preserves_all_request_fields(self) -> None:
        """Verify all AuthorizationRequest fields survive serialization."""
        from cyberred.tui.screens.authorization import SwarmSnapshot
        
        queue = AuthorizationQueue()
        
        request = AuthorizationRequest(
            id="req-full",
            request_type="lateral_move",
            agent_id="agent-007",
            target="192.168.100.50",
            proposed_action="SSH pivot with captured credentials",
            risk_level="HIGH",
            related_findings=[{"id": "finding-001", "severity": "CRITICAL"}],
            decision_context=["Previous success on similar target"],
            timestamp="2026-01-15T12:00:00+00:00",
            attck_technique="T1021.004",
            attck_tactic="Lateral Movement",
            origin_time_ns=1234567890,
        )
        request.swarm_snapshot = SwarmSnapshot(
            timestamp="2026-01-15T12:00:00+00:00",
            total_agents=100,
            by_status={"active": 80, "idle": 20},
            by_target={"192.168.100.0/24": 100},
        )
        
        queue.add_request(request)
        
        # Roundtrip through JSON
        json_str = json.dumps(queue.to_dict())
        restored = AuthorizationQueue.from_dict(json.loads(json_str))
        
        # Verify all fields
        req = restored.get_request_by_id("req-full")
        assert req is not None
        assert req.id == "req-full"
        assert req.request_type == "lateral_move"
        assert req.agent_id == "agent-007"
        assert req.target == "192.168.100.50"
        assert req.proposed_action == "SSH pivot with captured credentials"
        assert req.risk_level == "HIGH"
        assert req.related_findings == [{"id": "finding-001", "severity": "CRITICAL"}]
        assert req.decision_context == ["Previous success on similar target"]
        assert req.timestamp == "2026-01-15T12:00:00+00:00"
        assert req.attck_technique == "T1021.004"
        assert req.attck_tactic == "Lateral Movement"
        assert req.origin_time_ns == 1234567890


class TestAuthorizationQueueTUISync:
    """Integration tests for queue sync with TUI on attach/detach."""

    def test_queue_state_for_tui_attach_response(self) -> None:
        """Verify queue produces correct state for TUI attach response."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        queue.add_request(_create_request("req-1", "10.0.0.1", (now - timedelta(hours=1)).isoformat()))
        queue.add_request(_create_request("req-2", "10.0.0.2", now.isoformat()))
        
        # Get state for TUI
        data = queue.to_dict()
        pending_count = queue.get_pending_count()
        oldest_ts = queue.get_oldest_pending_timestamp()
        
        # TUI should receive:
        assert pending_count == 2
        assert oldest_ts is not None
        assert "requests" in data
        
        # Calculate age for TUI display
        if oldest_ts:
            age_seconds = (datetime.now(timezone.utc) - oldest_ts).total_seconds()
            assert age_seconds > 0  # Oldest should have positive age

    def test_queue_survives_simulated_detach_reattach(self) -> None:
        """Verify queue state is preserved across simulated TUI detach/reattach."""
        # Initial queue state
        queue = AuthorizationQueue()
        queue.add_request(_create_request("req-persistent", "172.16.0.1"))
        
        # Simulate detach: serialize to "Redis"
        stored_state = json.dumps(queue.to_dict())
        
        # Simulate daemon continues running, more requests added
        queue.add_request(_create_request("req-during-detach", "172.16.0.2"))
        
        # Update stored state
        stored_state = json.dumps(queue.to_dict())
        
        # Simulate reattach: new TUI gets state from "Redis"
        restored_data = json.loads(stored_state)
        reattached_queue = AuthorizationQueue.from_dict(restored_data)
        
        # Both requests should be present
        assert reattached_queue.get_pending_count() == 2
        assert reattached_queue.get_request_by_id("req-persistent") is not None
        assert reattached_queue.get_request_by_id("req-during-detach") is not None


class TestAuthorizationQueue24hAutoPauseIntegration:
    """Integration tests for 24h auto-pause with engagement state machine."""

    def test_24h_timeout_detection_with_mixed_ages(self) -> None:
        """Verify timeout detection works with requests of different ages."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        
        # Add requests with various ages
        queue.add_request(_create_request("req-recent", "10.0.0.1", now.isoformat()))
        queue.add_request(_create_request("req-1h", "10.0.0.2", (now - timedelta(hours=1)).isoformat()))
        queue.add_request(_create_request("req-23h", "10.0.0.3", (now - timedelta(hours=23)).isoformat()))
        
        # No timeout yet (oldest is 23h)
        assert queue.check_24h_timeout() is False
        
        # Add an old request
        queue.add_request(_create_request("req-25h", "10.0.0.4", (now - timedelta(hours=25)).isoformat()))
        
        # Now timeout should trigger
        assert queue.check_24h_timeout() is True

    def test_24h_timeout_clears_when_old_request_resolved(self) -> None:
        """Verify timeout state clears when old request is resolved."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        
        # Add old and new requests
        queue.add_request(_create_request("req-old", "10.0.0.1", (now - timedelta(hours=25)).isoformat()))
        queue.add_request(_create_request("req-new", "10.0.0.2", now.isoformat()))
        
        # Timeout detected
        assert queue.check_24h_timeout() is True
        
        # Resolve the old request
        queue.remove_request("req-old")
        
        # Timeout should clear
        assert queue.check_24h_timeout() is False


class TestAuthorizationQueueEventIntegration:
    """Integration tests for queue events with StreamEventType."""

    def test_auth_queue_updated_event_type_exists(self) -> None:
        """Verify AUTH_QUEUE_UPDATED event type is available."""
        from cyberred.daemon.streaming import StreamEventType
        
        assert hasattr(StreamEventType, "AUTH_QUEUE_UPDATED")
        assert StreamEventType.AUTH_QUEUE_UPDATED == "auth_queue_updated"

    def test_queue_event_payload_structure(self) -> None:
        """Verify queue can produce correct event payload structure."""
        queue = AuthorizationQueue()
        
        now = datetime.now(timezone.utc)
        queue.add_request(_create_request("req-1", "10.0.0.1", (now - timedelta(hours=1)).isoformat()))
        
        # Build event payload (as daemon would)
        oldest_ts = queue.get_oldest_pending_timestamp()
        age_seconds = (datetime.now(timezone.utc) - oldest_ts).total_seconds() if oldest_ts else 0
        
        payload = {
            "type": "auth_queue_updated",
            "pending_count": queue.get_pending_count(),
            "oldest_request_age_seconds": int(age_seconds),
            "engagement_id": "eng-123",
        }
        
        # Verify payload structure
        assert payload["type"] == "auth_queue_updated"
        assert payload["pending_count"] == 1
        assert payload["oldest_request_age_seconds"] >= 3600  # ~1 hour
        assert payload["engagement_id"] == "eng-123"


# Helper function
def _create_request(
    request_id: str,
    target: str,
    timestamp: str | None = None,
) -> AuthorizationRequest:
    """Create a test AuthorizationRequest."""
    return AuthorizationRequest(
        id=request_id,
        request_type="lateral_move",
        agent_id="agent-001",
        target=target,
        proposed_action="Test action",
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
    )
