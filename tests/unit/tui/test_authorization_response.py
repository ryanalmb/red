"""Unit tests for Authorization Response Handling (Story 10.2).

Tests the authorization audit logging with:
- AuditLogger interface for authorization events
- Audit entry format validation
- Audit logging on all response paths (APPROVED, DENIED, SKIPPED)
- Latency measurement in audit entries
- Batch apply flag in audit entries

TDD: RED Phase - Write failing tests first.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationAuditEntry Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationAuditEntry:
    """Tests for AuthorizationAuditEntry dataclass."""

    def test_import_audit_entry(self):
        """Test that AuthorizationAuditEntry can be imported."""
        from cyberred.core.audit import AuthorizationAuditEntry
        assert AuthorizationAuditEntry is not None

    def test_audit_entry_default_values(self):
        """Test AuthorizationAuditEntry default values."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
        )
        
        assert entry.event_type == "authorization_response"
        assert entry.request_id == "req-001"
        assert entry.decision == "APPROVED"
        assert entry.operator == "root"
        assert entry.timestamp is not None
        assert entry.constraints is None
        assert entry.batch_apply is False
        assert entry.auto_denied is False

    def test_audit_entry_with_constraints(self):
        """Test AuthorizationAuditEntry with constraints."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        constraints = {
            "time_limit": 300,
            "target_limit": 5,
            "specific_hosts_only": ["192.168.1.10"],
        }
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
            constraints=constraints,
        )
        
        assert entry.constraints == constraints

    def test_audit_entry_with_context(self):
        """Test AuthorizationAuditEntry with full context."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        context = {
            "target": "192.168.1.100",
            "agent_id": "recon-42",
            "risk_level": "HIGH",
            "request_type": "lateral_move",
        }
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="DENIED",
            operator="admin",
            context=context,
        )
        
        assert entry.context == context

    def test_audit_entry_with_swarm_snapshot(self):
        """Test AuthorizationAuditEntry with swarm snapshot."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        swarm_snapshot = {
            "total_agents": 50,
            "by_status": {"scanning": 30, "idle": 20},
        }
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
            swarm_snapshot=swarm_snapshot,
        )
        
        assert entry.swarm_snapshot == swarm_snapshot

    def test_audit_entry_with_latency(self):
        """Test AuthorizationAuditEntry with delivery latency."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
            delivery_latency_ms=45.2,
        )
        
        assert entry.delivery_latency_ms == 45.2

    def test_audit_entry_to_dict(self):
        """Test AuthorizationAuditEntry conversion to dictionary."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
            constraints={"time_limit": 300},
            batch_apply=True,
        )
        
        d = entry.to_dict()
        
        assert d["event_type"] == "authorization_response"
        assert d["request_id"] == "req-001"
        assert d["decision"] == "APPROVED"
        assert d["operator"] == "root"
        assert d["constraints"] == {"time_limit": 300}
        assert d["batch_apply"] is True
        assert "timestamp" in d

    def test_audit_entry_from_dict(self):
        """Test AuthorizationAuditEntry creation from dictionary."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        data = {
            "event_type": "authorization_response",
            "timestamp": "2026-01-28T12:00:00Z",
            "request_id": "req-001",
            "decision": "DENIED",
            "operator": "admin",
            "constraints": None,
            "context": {"target": "192.168.1.100"},
            "batch_apply": False,
            "auto_denied": False,
        }
        
        entry = AuthorizationAuditEntry.from_dict(data)
        
        assert entry.request_id == "req-001"
        assert entry.decision == "DENIED"
        assert entry.operator == "admin"


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationAuditLogger Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationAuditLogger:
    """Tests for AuthorizationAuditLogger class."""

    def test_import_audit_logger(self):
        """Test that AuthorizationAuditLogger can be imported."""
        from cyberred.core.audit import AuthorizationAuditLogger
        assert AuthorizationAuditLogger is not None

    def test_audit_logger_initialization(self):
        """Test AuthorizationAuditLogger initialization."""
        from cyberred.core.audit import AuthorizationAuditLogger
        
        redis_client = MagicMock()
        logger = AuthorizationAuditLogger(redis_client)
        
        assert logger._redis_client == redis_client
        assert logger._stream_name == "audit:stream"

    def test_audit_logger_custom_stream_name(self):
        """Test AuthorizationAuditLogger with custom stream name."""
        from cyberred.core.audit import AuthorizationAuditLogger
        
        redis_client = MagicMock()
        logger = AuthorizationAuditLogger(redis_client, stream_name="custom:audit")
        
        assert logger._stream_name == "custom:audit"

    @pytest.mark.asyncio
    async def test_log_approval(self):
        """Test logging an APPROVED authorization response."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
            constraints={"time_limit": 300},
        )
        
        entry_id = await logger.log(entry)
        
        assert entry_id == "1234567890-0"
        redis_client.xadd.assert_called_once()
        
        # Verify the call arguments
        call_args = redis_client.xadd.call_args
        assert call_args[0][0] == "audit:stream"  # stream name
        assert "event_type" in call_args[0][1] or isinstance(call_args[0][1], dict)

    @pytest.mark.asyncio
    async def test_log_denial(self):
        """Test logging a DENIED authorization response."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-1")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-002",
            decision="DENIED",
            operator="admin",
        )
        
        entry_id = await logger.log(entry)
        
        assert entry_id == "1234567890-1"
        redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_skip(self):
        """Test logging a SKIPPED authorization response."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-2")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-003",
            decision="SKIPPED",
            operator="user",
        )
        
        entry_id = await logger.log(entry)
        
        assert entry_id == "1234567890-2"

    @pytest.mark.asyncio
    async def test_log_auto_denied(self):
        """Test logging an auto-denied (timeout) authorization response."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-3")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-004",
            decision="DENIED",
            operator="system",
            auto_denied=True,
        )
        
        entry_id = await logger.log(entry)
        
        # Verify auto_denied flag is in the logged entry
        call_args = redis_client.xadd.call_args
        logged_data = call_args[0][1]
        assert logged_data.get("auto_denied") is True or "auto_denied" in str(logged_data)

    @pytest.mark.asyncio
    async def test_log_with_latency(self):
        """Test logging includes delivery latency measurement."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-4")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-005",
            decision="APPROVED",
            operator="root",
            delivery_latency_ms=123.45,
        )
        
        await logger.log(entry)
        
        # Verify latency is in the logged entry
        call_args = redis_client.xadd.call_args
        logged_data = call_args[0][1]
        assert "delivery_latency_ms" in str(logged_data)

    @pytest.mark.asyncio
    async def test_log_with_batch_apply(self):
        """Test logging includes batch_apply flag."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-5")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-006",
            decision="APPROVED",
            operator="root",
            batch_apply=True,
        )
        
        await logger.log(entry)
        
        # Verify batch_apply is in the logged entry
        call_args = redis_client.xadd.call_args
        logged_data = call_args[0][1]
        assert logged_data.get("batch_apply") is True or "batch_apply" in str(logged_data)

    @pytest.mark.asyncio
    async def test_log_error_handling(self):
        """Test audit logging handles errors gracefully."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        
        logger = AuthorizationAuditLogger(redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id="req-007",
            decision="APPROVED",
            operator="root",
        )
        
        # Should not raise, but return None on failure
        entry_id = await logger.log(entry)
        
        assert entry_id is None

    @pytest.mark.asyncio
    async def test_log_from_response_dict(self):
        """Test creating and logging audit entry from response dict."""
        from cyberred.core.audit import AuthorizationAuditLogger
        
        redis_client = AsyncMock()
        redis_client.xadd = AsyncMock(return_value="1234567890-6")
        
        logger = AuthorizationAuditLogger(redis_client)
        
        response = {
            "request_id": "req-008",
            "decision": "APPROVED",
            "operator": "root",
            "target": "192.168.1.100",
            "agent_id": "recon-42",
            "constraints": {"time_limit": 300},
            "batch_apply": True,
            "delivery_latency_ms": 50.0,
        }
        
        entry_id = await logger.log_response(response)
        
        assert entry_id == "1234567890-6"


# ─────────────────────────────────────────────────────────────────────────────
# Audit Entry Schema Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditEntrySchema:
    """Tests for audit entry schema compliance."""

    def test_audit_entry_has_required_fields(self):
        """Test audit entry has all required fields per architecture spec."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
        )
        
        d = entry.to_dict()
        
        # Required fields per architecture.md
        required_fields = [
            "event_type",
            "timestamp",
            "request_id",
            "decision",
            "operator",
        ]
        
        for field in required_fields:
            assert field in d, f"Missing required field: {field}"

    def test_audit_entry_event_type_is_authorization_response(self):
        """Test event_type is always 'authorization_response'."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
        )
        
        assert entry.event_type == "authorization_response"
        assert entry.to_dict()["event_type"] == "authorization_response"

    def test_audit_entry_timestamp_is_iso8601(self):
        """Test timestamp is in ISO 8601 format."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="root",
        )
        
        # Should be parseable as ISO 8601
        timestamp = entry.timestamp
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None

    def test_audit_entry_decision_values(self):
        """Test decision field accepts valid values."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        # Valid decisions
        for decision in ["APPROVED", "DENIED", "SKIPPED"]:
            entry = AuthorizationAuditEntry(
                request_id="req-001",
                decision=decision,
                operator="root",
            )
            assert entry.decision == decision


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT_STREAM_NAME constant test
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditConstants:
    """Tests for audit module constants."""

    def test_audit_stream_name_constant(self):
        """Test AUDIT_STREAM_NAME constant exists."""
        from cyberred.core.audit import AUDIT_STREAM_NAME
        
        assert AUDIT_STREAM_NAME == "audit:stream"


class TestAuditLoggerSingleton:
    """Tests for audit logger singleton functions."""

    def test_get_audit_logger_returns_none_initially(self):
        """Test get_audit_logger returns None when not initialized."""
        from cyberred.core.audit import get_audit_logger, set_audit_logger, _audit_logger_instance
        import cyberred.core.audit as audit_module
        
        # Reset singleton
        audit_module._audit_logger_instance = None
        
        result = get_audit_logger()
        assert result is None

    def test_set_audit_logger(self):
        """Test set_audit_logger sets the instance."""
        from cyberred.core.audit import get_audit_logger, set_audit_logger, AuthorizationAuditLogger
        import cyberred.core.audit as audit_module
        
        mock_redis = MagicMock()
        logger = AuthorizationAuditLogger(mock_redis)
        
        set_audit_logger(logger)
        
        result = get_audit_logger()
        assert result is logger
        
        # Cleanup
        audit_module._audit_logger_instance = None

    def test_init_audit_logger(self):
        """Test init_audit_logger creates and sets logger."""
        from cyberred.core.audit import init_audit_logger, get_audit_logger
        import cyberred.core.audit as audit_module
        
        mock_redis = MagicMock()
        
        logger = init_audit_logger(mock_redis)
        
        assert logger is not None
        assert get_audit_logger() is logger
        
        # Cleanup
        audit_module._audit_logger_instance = None
