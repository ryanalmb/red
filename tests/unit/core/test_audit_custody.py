"""Unit tests for Chain of Custody audit logging.

Story 13.11: Evidence Chain of Custody

Tests for CustodyEvent dataclass and CustodyAuditLogger.
These tests should FAIL until implementation is complete (RED phase).
"""

from __future__ import annotations

import hashlib
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Import will fail until implementation exists - this is expected in RED phase
# from cyberred.core.audit import CustodyEvent, CustodyAuditLogger


class TestCustodyEventDataclass:
    """Test CustodyEvent dataclass structure and serialization.
    
    Task 1: Write Failing Unit Tests for Chain of Custody Logging (AC: 1)
    """
    
    def test_custody_event_has_required_fields(self):
        """Test CustodyEvent includes all required fields per spec."""
        from cyberred.core.audit import CustodyEvent
        
        event = CustodyEvent(
            event_id="evt-123",
            evidence_id="evidence-456",
            engagement_id="engagement-789",
            operator="root",
            action="ACCESS",
            timestamp="2026-02-12T09:30:00.000000+00:00",
            file_hash="a1b2c3d4e5f6",
            file_hash_before=None,
            details={"access_reason": "manual review"},
            signed_timestamp={
                "timestamp": "2026-02-12T09:30:00.000000+00:00",
                "event_hash": "a1b2c3d4e5f6",
                "signature": "base64sig",
            },
        )
        
        assert event.event_id == "evt-123"
        assert event.evidence_id == "evidence-456"
        assert event.engagement_id == "engagement-789"
        assert event.operator == "root"
        assert event.action == "ACCESS"
        assert event.file_hash == "a1b2c3d4e5f6"
        assert event.file_hash_before is None
        assert event.details == {"access_reason": "manual review"}
        assert event.signed_timestamp is not None
    
    def test_custody_event_to_dict_serialization(self):
        """Test CustodyEvent.to_dict() serializes all fields correctly."""
        from cyberred.core.audit import CustodyEvent
        
        event = CustodyEvent(
            event_id="evt-123",
            evidence_id="evidence-456",
            engagement_id="engagement-789",
            operator="root",
            action="EXPORT",
            timestamp="2026-02-12T09:30:00.000000+00:00",
            file_hash="a1b2c3",
            file_hash_before=None,
            details={"export_path": "/tmp/export.zip"},
            signed_timestamp={"timestamp": "2026-02-12T09:30:00.000000+00:00", "signature": "sig"},
        )
        
        result = event.to_dict()
        
        assert result["event_id"] == "evt-123"
        assert result["evidence_id"] == "evidence-456"
        assert result["operator"] == "root"
        assert result["action"] == "EXPORT"
        assert result["file_hash"] == "a1b2c3"
        assert result["details"]["export_path"] == "/tmp/export.zip"
        assert "signed_timestamp" in result
    
    def test_custody_event_from_dict_deserialization(self):
        """Test CustodyEvent.from_dict() deserializes correctly."""
        from cyberred.core.audit import CustodyEvent
        
        data = {
            "event_id": "evt-123",
            "evidence_id": "evidence-456",
            "engagement_id": "engagement-789",
            "operator": "root",
            "action": "CREATE",
            "timestamp": "2026-02-12T09:30:00.000000+00:00",
            "file_hash": "a1b2c3",
            "file_hash_before": None,
            "details": {"filename": "screenshot.png"},
            "signed_timestamp": {"timestamp": "2026-02-12T09:30:00.000000+00:00", "signature": "sig"},
        }
        
        event = CustodyEvent.from_dict(data)
        
        assert event.event_id == "evt-123"
        assert event.evidence_id == "evidence-456"
        assert event.action == "CREATE"
        assert event.details["filename"] == "screenshot.png"
    
    def test_custody_event_supports_modify_action_with_before_hash(self):
        """Test CustodyEvent handles MODIFY action with file_hash_before field."""
        from cyberred.core.audit import CustodyEvent
        
        event = CustodyEvent(
            event_id="evt-123",
            evidence_id="evidence-456",
            engagement_id="engagement-789",
            operator="root",
            action="MODIFY",
            timestamp="2026-02-12T09:30:00.000000+00:00",
            file_hash="new_hash",
            file_hash_before="old_hash",
            details={"reason": "redaction"},
            signed_timestamp=None,
        )
        
        assert event.action == "MODIFY"
        assert event.file_hash_before == "old_hash"
        assert event.file_hash == "new_hash"


class TestCustodyAuditLogger:
    """Test CustodyAuditLogger logs custody events to Redis Streams.
    
    Task 1: Write Failing Unit Tests for Chain of Custody Logging (AC: 1)
    """
    
    @pytest.mark.asyncio
    async def test_custody_logger_logs_to_redis_stream(self):
        """Test custody logger writes event to Redis Streams."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        event_id = await logger.log_custody_event(
            evidence_id="evidence-456",
            operator="root",
            action="ACCESS",
            file_hash="a1b2c3",
            details={"access_reason": "review"},
        )
        
        assert event_id is not None
        mock_redis.xadd.assert_called_once()
        
        # Verify stream key
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "custody:engagement-123"
    
    @pytest.mark.asyncio
    async def test_custody_logger_includes_signed_timestamp(self):
        """Test custody events include cryptographically signed timestamps."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        await logger.log_custody_event(
            evidence_id="evidence-456",
            operator="root",
            action="EXPORT",
            file_hash="a1b2c3",
        )
        
        # Check that xadd was called with signed_timestamp field
        call_args = mock_redis.xadd.call_args
        event_dict = call_args[0][1]
        assert "signed_timestamp" in event_dict
        assert event_dict["signed_timestamp"] is not None
    
    @pytest.mark.asyncio
    async def test_custody_logger_generates_unique_event_ids(self):
        """Test each custody event gets unique event_id (UUID)."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        event_id_1 = await logger.log_custody_event(
            evidence_id="evidence-1",
            operator="root",
            action="ACCESS",
            file_hash="hash1",
        )
        
        event_id_2 = await logger.log_custody_event(
            evidence_id="evidence-2",
            operator="root",
            action="ACCESS",
            file_hash="hash2",
        )
        
        assert event_id_1 != event_id_2
    
    @pytest.mark.asyncio
    async def test_custody_logger_action_types(self):
        """Test custody logger supports all action types."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        actions = ["CREATE", "ACCESS", "EXPORT", "MODIFY", "DELETE"]
        
        for action in actions:
            await logger.log_custody_event(
                evidence_id="evidence-456",
                operator="root",
                action=action,
                file_hash="a1b2c3",
            )
        
        assert mock_redis.xadd.call_count == len(actions)


class TestCustodyChainReconstruction:
    """Test custody chain reconstruction from Redis Streams.
    
    Task 3: Write Failing Unit Tests for Chain of Custody Reconstruction (AC: 1)
    """
    
    @pytest.mark.asyncio
    async def test_get_custody_chain_returns_all_events_for_evidence(self):
        """Test get_custody_chain() returns all events for specific evidence_id."""
        from cyberred.core.audit import CustodyAuditLogger, CustodyEvent
        
        mock_redis = AsyncMock()
        
        # Mock Redis stream data - must include all required fields
        mock_redis.xrange = AsyncMock(return_value=[
            ("1-0", {
                "event_id": "evt-1",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "operator": "system",
                "action": "CREATE",
                "timestamp": "2026-02-10T10:00:00+00:00",
                "file_hash": "hash1",
            }),
            ("2-0", {
                "event_id": "evt-2",
                "evidence_id": "evidence-999",
                "engagement_id": "engagement-123",
                "operator": "root",
                "action": "ACCESS",
                "timestamp": "2026-02-10T11:00:00+00:00",
                "file_hash": "hash2",
            }),
            ("3-0", {
                "event_id": "evt-3",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "operator": "root",
                "action": "EXPORT",
                "timestamp": "2026-02-10T12:00:00+00:00",
                "file_hash": "hash1",
            }),
        ])
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        chain = await logger.get_custody_chain("evidence-456")
        
        assert len(chain) == 2
        assert all(isinstance(event, CustodyEvent) for event in chain)
        assert chain[0].action == "CREATE"
        assert chain[1].action == "EXPORT"
    
    @pytest.mark.asyncio
    async def test_get_custody_chain_ordered_chronologically(self):
        """Test custody chain is ordered oldest to newest."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        
        # Mock events out of order - must include all required fields
        mock_redis.xrange = AsyncMock(return_value=[
            ("3-0", {
                "event_id": "evt-3",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "operator": "root",
                "action": "EXPORT",
                "timestamp": "2026-02-10T12:00:00+00:00",
                "file_hash": "hash1",
            }),
            ("1-0", {
                "event_id": "evt-1",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "operator": "system",
                "action": "CREATE",
                "timestamp": "2026-02-10T10:00:00+00:00",
                "file_hash": "hash1",
            }),
            ("2-0", {
                "event_id": "evt-2",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "operator": "root",
                "action": "ACCESS",
                "timestamp": "2026-02-10T11:00:00+00:00",
                "file_hash": "hash1",
            }),
        ])
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        chain = await logger.get_custody_chain("evidence-456")
        
        # Should be sorted by timestamp
        assert chain[0].action == "CREATE"  # 10:00
        assert chain[1].action == "ACCESS"  # 11:00
        assert chain[2].action == "EXPORT"  # 12:00
    
    @pytest.mark.asyncio
    async def test_get_custody_chain_empty_for_nonexistent_evidence(self):
        """Test get_custody_chain() returns empty list for non-existent evidence."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xrange = AsyncMock(return_value=[])
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        chain = await logger.get_custody_chain("nonexistent-evidence")
        
        assert chain == []
    
    @pytest.mark.asyncio
    async def test_get_custody_chain_includes_creation_event(self):
        """Test custody chain includes initial CREATE event."""
        from cyberred.core.audit import CustodyAuditLogger
        
        mock_redis = AsyncMock()
        mock_redis.xrange = AsyncMock(return_value=[
            ("1-0", {
                "event_id": "evt-1",
                "evidence_id": "evidence-456",
                "engagement_id": "engagement-123",
                "action": "CREATE",
                "timestamp": "2026-02-10T10:00:00+00:00",
                "operator": "system",
                "file_hash": "a1b2c3",
            }),
        ])
        
        logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        chain = await logger.get_custody_chain("evidence-456")
        
        assert len(chain) > 0
        assert chain[0].action == "CREATE"
        assert chain[0].operator == "system"
