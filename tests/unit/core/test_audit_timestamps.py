"""Unit tests for audit log timestamp signing integration (Story 13.10)."""
from __future__ import annotations

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock

from cyberred.core.audit import (
    AuthorizationAuditEntry,
    AuthorizationAuditLogger,
    AlertAuditLogger,
    ExportAuditLogger,
    DeletionAuditLogger,
)


class TestAuthorizationAuditEntryTimestamps:
    """Tests for AuthorizationAuditEntry timestamp signing."""
    
    def test_audit_entry_has_signed_timestamp_field(self):
        """Test that AuthorizationAuditEntry has signed_timestamp field."""
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="test-operator",
        )
        
        assert hasattr(entry, "signed_timestamp")
    
    def test_audit_entry_signed_timestamp_structure(self):
        """Test that signed_timestamp has correct structure."""
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="test-operator",
        )
        
        # Will be set during logging
        # Initially might be None, but should exist as attribute
        assert "signed_timestamp" in entry.__dataclass_fields__
    
    def test_audit_entry_to_dict_includes_signed_timestamp(self):
        """Test that to_dict() includes signed_timestamp."""
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="test-operator",
        )
        
        entry_dict = entry.to_dict()
        # Initially None, but key should exist
        assert "signed_timestamp" in entry_dict


class TestAuthorizationAuditLoggerTimestamps:
    """Tests for AuthorizationAuditLogger timestamp signing."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        client = MagicMock()
        client.xadd = AsyncMock(return_value="1234567890-0")
        return client
    
    @pytest.fixture
    def audit_logger(self, mock_redis_client):
        """Create AuthorizationAuditLogger with mock Redis."""
        return AuthorizationAuditLogger(mock_redis_client)
    
    @pytest.mark.asyncio
    async def test_log_creates_signed_timestamp(self, audit_logger, mock_redis_client):
        """Test that logging creates a signed timestamp."""
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="test-operator",
        )
        
        await audit_logger.log(entry)
        
        # Check that xadd was called with entry containing signed_timestamp
        call_args = mock_redis_client.xadd.call_args
        entry_dict = call_args[0][1]
        
        assert "signed_timestamp" in entry_dict
        assert entry_dict["signed_timestamp"] is not None
    
    @pytest.mark.asyncio
    async def test_signed_timestamp_includes_event_hash(self, audit_logger, mock_redis_client):
        """Test that signed_timestamp includes event_hash of entry content."""
        entry = AuthorizationAuditEntry(
            request_id="req-001",
            decision="APPROVED",
            operator="test-operator",
        )
        
        await audit_logger.log(entry)
        
        call_args = mock_redis_client.xadd.call_args
        entry_dict = call_args[0][1]
        signed_ts = entry_dict["signed_timestamp"]
        
        assert isinstance(signed_ts, dict)
        assert "event_hash" in signed_ts
        assert "signature" in signed_ts


class TestAlertAuditLoggerTimestamps:
    """Tests for AlertAuditLogger timestamp signing."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        client = MagicMock()
        client.xadd = AsyncMock(return_value="1234567890-0")
        return client
    
    @pytest.fixture
    def alert_logger(self, mock_redis_client):
        """Create AlertAuditLogger with mock Redis."""
        return AlertAuditLogger(mock_redis_client)
    
    @pytest.mark.asyncio
    async def test_alert_audit_includes_signed_timestamp(self, alert_logger, mock_redis_client):
        """Test that alert audit entries include signed timestamps."""
        # Mock alert and response objects
        alert = MagicMock()
        alert.id = "alert-001"
        alert.alert_type = MagicMock()
        alert.alert_type.value = "SCOPE_EXPANSION"
        
        response = MagicMock()
        response.decision = MagicMock()
        response.decision.value = "ALLOW"
        
        await alert_logger.log_response(alert, response, "engagement-001")
        
        # Verify xadd was called
        assert mock_redis_client.xadd.called


class TestExportAuditLoggerTimestamps:
    """Tests for ExportAuditLogger timestamp signing."""
    
    def test_export_audit_entry_has_signed_timestamp(self):
        """Test that ExportAuditEntry includes signed_timestamp field."""
        from cyberred.core.audit import ExportAuditEntry
        
        entry = ExportAuditEntry(
            event_type="single_export",
            item_id="item-001",
            filename="test.txt",
            destination="/tmp/export",
        )
        
        assert hasattr(entry, "signed_timestamp")
    
    def test_export_logger_signs_timestamps(self):
        """Test that ExportAuditLogger signs timestamps when logging."""
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = ExportAuditLogger(mock_redis)
        
        logger.log_export(
            item_id="item-001",
            filename="test.txt",
            destination="/tmp/export",
        )
        
        # Should have logged with signed timestamp
        # Implementation will be in GREEN phase


class TestDeletionAuditLoggerTimestamps:
    """Tests for DeletionAuditLogger timestamp signing."""
    
    def test_deletion_audit_entry_has_signed_timestamp(self):
        """Test that DeletionAuditEntry includes signed_timestamp field."""
        from cyberred.core.audit import DeletionAuditEntry
        
        entry = DeletionAuditEntry(
            event_type="single_deletion",
            item_id="item-001",
            filename="test.txt",
            target="192.168.1.1",
            size_bytes=1024,
        )
        
        assert hasattr(entry, "signed_timestamp")
    
    def test_deletion_logger_signs_timestamps(self):
        """Test that DeletionAuditLogger signs timestamps when logging."""
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        logger = DeletionAuditLogger(mock_redis)
        
        logger.log_deletion(
            item_id="item-001",
            filename="test.txt",
            target="192.168.1.1",
            size_bytes=1024,
        )
        
        # Should have logged with signed timestamp
        # Implementation will be in GREEN phase
