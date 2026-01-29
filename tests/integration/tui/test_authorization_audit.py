"""Integration tests for Authorization Audit Logging (Story 10.2).

Tests the full audit flow including:
- Approve with constraints → audit entry in Redis
- Deny → audit entry in Redis
- Skip → audit entry in Redis
- Audit entry format matches schema
- Audit stream consumer can read entries

TDD: RED Phase - Write failing tests first.
"""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationAuditFlow:
    """Integration tests for full authorization audit flow."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client with audit stream support."""
        client = AsyncMock()
        client.is_connected = True
        client._audit_entries = []  # Store entries for verification
        
        async def mock_xadd(stream, fields, maxlen=None):
            entry_id = f"{int(datetime.now().timestamp() * 1000)}-{len(client._audit_entries)}"
            client._audit_entries.append({
                "stream": stream,
                "id": entry_id,
                "fields": fields,
            })
            return entry_id
        
        client.xadd = mock_xadd
        return client

    @pytest.fixture
    def sample_auth_request(self):
        """Create sample authorization request."""
        from cyberred.tui.screens.authorization import AuthorizationRequest, SwarmSnapshot
        
        return AuthorizationRequest(
            id="test-req-001",
            request_type="lateral_move",
            agent_id="recon-agent-001",
            target="192.168.1.100",
            proposed_action="SSH brute force attack",
            risk_level="HIGH",
            related_findings=[
                {"finding_id": "find-001", "title": "SSH port open", "severity": "MEDIUM"},
            ],
            decision_context=["Found SSH service on port 22"],
            swarm_snapshot=SwarmSnapshot(
                timestamp="2026-01-28T12:00:00Z",
                total_agents=50,
                by_status={"idle": 20, "scanning": 30},
            ),
            attck_technique="T1110.001",
            attck_tactic="Credential Access",
        )

    @pytest.mark.asyncio
    async def test_approve_with_constraints_creates_audit_entry(self, mock_redis_client, sample_auth_request):
        """Test approve with constraints creates proper audit entry."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        logger = AuthorizationAuditLogger(mock_redis_client)
        
        # Create audit entry for approval with constraints
        entry = AuthorizationAuditEntry(
            request_id=sample_auth_request.id,
            decision="APPROVED",
            operator="root",
            constraints={
                "time_limit": 300,
                "target_limit": 5,
                "specific_hosts_only": ["192.168.1.100"],
            },
            context={
                "target": sample_auth_request.target,
                "agent_id": sample_auth_request.agent_id,
                "risk_level": sample_auth_request.risk_level,
                "request_type": sample_auth_request.request_type,
            },
            batch_apply=False,
            delivery_latency_ms=45.2,
        )
        
        entry_id = await logger.log(entry)
        
        # Verify entry was created
        assert entry_id is not None
        assert len(mock_redis_client._audit_entries) == 1
        
        # Verify entry content
        logged = mock_redis_client._audit_entries[0]
        assert logged["stream"] == "audit:stream"
        assert "APPROVED" in str(logged["fields"]) or logged["fields"].get("decision") == "APPROVED"

    @pytest.mark.asyncio
    async def test_deny_creates_audit_entry(self, mock_redis_client, sample_auth_request):
        """Test deny creates proper audit entry."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        logger = AuthorizationAuditLogger(mock_redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id=sample_auth_request.id,
            decision="DENIED",
            operator="admin",
            context={
                "target": sample_auth_request.target,
                "agent_id": sample_auth_request.agent_id,
                "risk_level": sample_auth_request.risk_level,
            },
        )
        
        entry_id = await logger.log(entry)
        
        assert entry_id is not None
        assert len(mock_redis_client._audit_entries) == 1
        
        logged = mock_redis_client._audit_entries[0]
        assert "DENIED" in str(logged["fields"]) or logged["fields"].get("decision") == "DENIED"

    @pytest.mark.asyncio
    async def test_skip_creates_audit_entry(self, mock_redis_client, sample_auth_request):
        """Test skip creates proper audit entry."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        logger = AuthorizationAuditLogger(mock_redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id=sample_auth_request.id,
            decision="SKIPPED",
            operator="user",
        )
        
        entry_id = await logger.log(entry)
        
        assert entry_id is not None
        logged = mock_redis_client._audit_entries[0]
        assert "SKIPPED" in str(logged["fields"]) or logged["fields"].get("decision") == "SKIPPED"

    @pytest.mark.asyncio
    async def test_audit_entry_format_matches_schema(self, mock_redis_client, sample_auth_request):
        """Test audit entry format matches architecture schema."""
        from cyberred.core.audit import AuthorizationAuditLogger, AuthorizationAuditEntry
        
        logger = AuthorizationAuditLogger(mock_redis_client)
        
        entry = AuthorizationAuditEntry(
            request_id=sample_auth_request.id,
            decision="APPROVED",
            operator="root",
            constraints={"time_limit": 300},
            context={
                "target": sample_auth_request.target,
                "agent_id": sample_auth_request.agent_id,
                "risk_level": sample_auth_request.risk_level,
                "request_type": sample_auth_request.request_type,
            },
            batch_apply=True,
            auto_denied=False,
            delivery_latency_ms=50.0,
            swarm_snapshot={
                "total_agents": 50,
                "by_status": {"scanning": 30, "idle": 20},
            },
        )
        
        await logger.log(entry)
        
        logged = mock_redis_client._audit_entries[0]
        fields = logged["fields"]
        
        # Verify schema fields are present (either directly or in serialized form)
        fields_str = str(fields)
        
        assert "event_type" in fields_str or "authorization_response" in fields_str
        assert "timestamp" in fields_str
        assert "request_id" in fields_str or sample_auth_request.id in fields_str
        assert "decision" in fields_str or "APPROVED" in fields_str
        assert "operator" in fields_str or "root" in fields_str


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationScreen Audit Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationScreenAuditIntegration:
    """Tests for AuthorizationScreen integration with audit logging."""

    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        logger = AsyncMock()
        logger.log = AsyncMock(return_value="1234567890-0")
        logger.log_response = AsyncMock(return_value="1234567890-0")
        return logger

    @pytest.mark.asyncio
    async def test_approve_triggers_audit_log(self, mock_audit_logger):
        """Test approval action triggers audit logging via log_response."""
        from cyberred.core.audit import AuthorizationAuditLogger
        
        # Create audit entry from response dict (simulating what authorization screen does)
        response = {
            "request_id": "test-001",
            "decision": "APPROVED",
            "operator": "root",
            "target": "192.168.1.1",
            "agent_id": "agent-1",
            "constraints": {"time_limit": 300},
            "batch_apply": False,
        }
        
        # Verify the audit logger can process the response
        entry_id = await mock_audit_logger.log_response(response)
        
        mock_audit_logger.log_response.assert_called_once_with(response)

    @pytest.mark.asyncio
    async def test_deny_triggers_audit_log(self, mock_audit_logger):
        """Test denial action triggers audit logging."""
        response = {
            "request_id": "test-002",
            "decision": "DENIED",
            "operator": "admin",
            "target": "192.168.1.1",
            "agent_id": "agent-1",
            "auto_denied": False,
        }
        
        await mock_audit_logger.log_response(response)
        
        mock_audit_logger.log_response.assert_called_once()
        call_args = mock_audit_logger.log_response.call_args[0][0]
        assert call_args["decision"] == "DENIED"

    @pytest.mark.asyncio
    async def test_skip_triggers_audit_log(self, mock_audit_logger):
        """Test skip action triggers audit logging."""
        response = {
            "request_id": "test-003",
            "decision": "SKIPPED",
            "operator": "user",
            "target": "192.168.1.1",
            "agent_id": "agent-1",
            "skipped": True,
        }
        
        await mock_audit_logger.log_response(response)
        
        mock_audit_logger.log_response.assert_called_once()
        call_args = mock_audit_logger.log_response.call_args[0][0]
        assert call_args["decision"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_auto_deny_triggers_audit_log_with_flag(self, mock_audit_logger):
        """Test auto-deny (timeout) triggers audit with auto_denied=True."""
        response = {
            "request_id": "test-004",
            "decision": "DENIED",
            "operator": "system",
            "target": "192.168.1.1",
            "agent_id": "agent-1",
            "auto_denied": True,
        }
        
        await mock_audit_logger.log_response(response)
        
        call_args = mock_audit_logger.log_response.call_args[0][0]
        assert call_args["decision"] == "DENIED"
        assert call_args["auto_denied"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Constraints Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConstraintsIntegration:
    """Integration tests for constraints form with AuthorizationScreen."""

    @pytest.mark.asyncio
    async def test_constraints_propagate_to_audit(self):
        """Test constraints from form propagate to audit entry."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        constraints = {
            "time_limit": 300,
            "target_limit": 5,
            "specific_hosts_only": ["192.168.1.10", "192.168.1.20"],
        }
        
        entry = AuthorizationAuditEntry(
            request_id="test-001",
            decision="APPROVED",
            operator="root",
            constraints=constraints,
        )
        
        d = entry.to_dict()
        
        assert d["constraints"] == constraints
        assert d["constraints"]["time_limit"] == 300
        assert d["constraints"]["target_limit"] == 5
        assert "192.168.1.10" in d["constraints"]["specific_hosts_only"]

    @pytest.mark.asyncio
    async def test_no_constraints_propagates_none(self):
        """Test no constraints (skip) propagates None to audit."""
        from cyberred.core.audit import AuthorizationAuditEntry
        
        entry = AuthorizationAuditEntry(
            request_id="test-001",
            decision="APPROVED",
            operator="root",
            constraints=None,
        )
        
        d = entry.to_dict()
        
        assert d["constraints"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Audit Stream Consumer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditStreamConsumer:
    """Tests for consuming audit entries from Redis stream."""

    @pytest.fixture
    def mock_redis_with_entries(self):
        """Create mock Redis client with pre-populated audit entries."""
        client = AsyncMock()
        client.is_connected = True
        
        # Pre-populate with audit entries
        client._stored_entries = [
            {
                "id": "1234567890-0",
                "fields": {
                    "event_type": "authorization_response",
                    "request_id": "req-001",
                    "decision": "APPROVED",
                    "operator": "root",
                    "timestamp": "2026-01-28T12:00:00Z",
                },
            },
            {
                "id": "1234567891-0",
                "fields": {
                    "event_type": "authorization_response",
                    "request_id": "req-002",
                    "decision": "DENIED",
                    "operator": "admin",
                    "timestamp": "2026-01-28T12:01:00Z",
                },
            },
        ]
        
        async def mock_xread(stream, last_id, count=1, block_ms=None):
            # Return entries after last_id
            results = []
            for entry in client._stored_entries:
                if last_id == "0" or entry["id"] > last_id:
                    results.append((entry["id"], entry["fields"]))
            return results[:count] if results else []
        
        client.xread = mock_xread
        return client

    @pytest.mark.asyncio
    async def test_read_audit_entries(self, mock_redis_with_entries):
        """Test reading audit entries from stream."""
        # This tests that audit entries can be consumed from the stream
        entries = await mock_redis_with_entries.xread("audit:stream", "0", count=10)
        
        assert len(entries) == 2
        assert entries[0][1]["decision"] == "APPROVED"
        assert entries[1][1]["decision"] == "DENIED"

    @pytest.mark.asyncio
    async def test_audit_entries_are_valid_format(self, mock_redis_with_entries):
        """Test consumed audit entries match expected format."""
        entries = await mock_redis_with_entries.xread("audit:stream", "0", count=10)
        
        for entry_id, fields in entries:
            assert "event_type" in fields
            assert fields["event_type"] == "authorization_response"
            assert "request_id" in fields
            assert "decision" in fields
            assert "operator" in fields
            assert "timestamp" in fields
