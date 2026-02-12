"""Unit tests for EvidenceStore custody integration.

Story 13.11: Evidence Chain of Custody

Tests for EvidenceStore custody logging integration.
These tests should FAIL until implementation is complete (RED phase).
"""

from __future__ import annotations

import hashlib
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from cyberred.storage.evidence_store import EvidenceStore, EvidenceType


class TestEvidenceStoreCustodyIntegration:
    """Test EvidenceStore logs custody events.
    
    Task 2: Write Failing Unit Tests for EvidenceStore Integration (AC: 1)
    """
    
    def test_evidence_store_accepts_custody_logger_in_constructor(self):
        """Test EvidenceStore constructor accepts optional custody_logger parameter."""
        
        
        encryption_key = b"0" * 32
        mock_custody_logger = MagicMock()
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        assert store.custody_logger is mock_custody_logger
    
    def test_get_evidence_requires_operator_parameter(self):
        """Test get_evidence() now requires operator parameter for custody tracking."""
        
        
        encryption_key = b"0" * 32
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
        )
        
        # Store evidence first
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # get_evidence should require operator parameter
        content = store.get_evidence(
            evidence_id=item.id,
            operator="root",
        )
        
        assert content == b"test data"
    
    @pytest.mark.asyncio
    async def test_get_evidence_logs_custody_access_event(self):
        """Test get_evidence() logs ACCESS custody event."""
        
        
        encryption_key = b"0" * 32
        mock_custody_logger = MagicMock()
        mock_custody_logger.log_custody_event = AsyncMock(return_value="evt-123")
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        # Store evidence
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Reset mock after store (which also logs CREATE event)
        mock_custody_logger.log_custody_event.reset_mock()
        
        # Access evidence
        content = store.get_evidence(
            evidence_id=item.id,
            operator="root",
            access_reason="manual review",
        )
        
        # Verify custody event was logged (only ACCESS, not CREATE)
        mock_custody_logger.log_custody_event.assert_called_once()
        call_args = mock_custody_logger.log_custody_event.call_args
        
        assert call_args.kwargs["evidence_id"] == item.id
        assert call_args.kwargs["operator"] == "root"
        assert call_args.kwargs["action"] == "ACCESS"
        assert call_args.kwargs["file_hash"] == item.sha256_hash
        assert call_args.kwargs["details"]["access_reason"] == "manual review"
    
    @pytest.mark.asyncio
    async def test_store_evidence_logs_creation_event(self):
        """Test store_evidence() logs CREATE custody event."""
        
        
        encryption_key = b"0" * 32
        mock_custody_logger = MagicMock()
        mock_custody_logger.log_custody_event = AsyncMock(return_value="evt-123")
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        # Store evidence with operator
        item = store.store_evidence(
            content=b"test data",
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
            operator="root",
        )
        
        # Verify custody event was logged
        mock_custody_logger.log_custody_event.assert_called_once()
        call_args = mock_custody_logger.log_custody_event.call_args
        
        assert call_args.kwargs["evidence_id"] == item.id
        assert call_args.kwargs["operator"] == "root"
        assert call_args.kwargs["action"] == "CREATE"
        assert call_args.kwargs["file_hash"] == item.sha256_hash
        assert call_args.kwargs["details"]["filename"] == "screenshot.png"
        assert call_args.kwargs["details"]["source_agent"] == "recon-01"
    
    def test_store_evidence_without_custody_logger_works(self):
        """Test store_evidence() works when custody_logger is None."""
        
        
        encryption_key = b"0" * 32
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=None,
        )
        
        # Should not raise error even without custody logger
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        assert item is not None
    
    @pytest.mark.asyncio
    async def test_get_evidence_includes_file_hash_in_custody_event(self):
        """Test custody event includes current file hash."""
        
        
        encryption_key = b"0" * 32
        mock_custody_logger = MagicMock()
        mock_custody_logger.log_custody_event = AsyncMock(return_value="evt-123")
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        content = b"test data for hashing"
        expected_hash = hashlib.sha256(content).hexdigest()
        
        item = store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Reset mock for access test
        mock_custody_logger.log_custody_event.reset_mock()
        
        # Access evidence
        store.get_evidence(
            evidence_id=item.id,
            operator="root",
        )
        
        # Verify file_hash in custody event matches SHA-256
        call_args = mock_custody_logger.log_custody_event.call_args
        assert call_args.kwargs["file_hash"] == expected_hash
    
    def test_get_evidence_optional_access_reason(self):
        """Test get_evidence() accepts optional access_reason parameter."""
        
        
        encryption_key = b"0" * 32
        mock_custody_logger = MagicMock()
        mock_custody_logger.log_custody_event = AsyncMock(return_value="evt-123")
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Reset mock
        mock_custody_logger.log_custody_event.reset_mock()
        
        # Access without reason
        store.get_evidence(
            evidence_id=item.id,
            operator="root",
        )
        
        call_args = mock_custody_logger.log_custody_event.call_args
        assert "access_reason" in call_args.kwargs["details"]
        assert call_args.kwargs["details"]["access_reason"] == "retrieval"


class TestCustodyReportGeneration:
    """Test custody report generation.
    
    Task 4: Write Failing Unit Tests for Custody Report Generation (AC: 1)
    """
    
    @pytest.mark.asyncio
    async def test_generate_custody_report_creates_json_report(self):
        """Test generate_custody_report() creates JSON report."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        encryption_key = b"0" * 32
        mock_redis = AsyncMock()
        mock_custody_logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        # Store evidence
        item = store.store_evidence(
            content=b"test data",
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        
        # Generate custody report
        report = await store.generate_custody_report(item.id)
        
        assert report is not None
        assert "report_version" in report
        assert "evidence" in report
        assert "custody_chain" in report
        assert report["evidence"]["id"] == item.id
    
    @pytest.mark.asyncio
    async def test_custody_report_includes_evidence_metadata(self):
        """Test custody report includes evidence metadata."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        encryption_key = b"0" * 32
        mock_redis = AsyncMock()
        mock_custody_logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        item = store.store_evidence(
            content=b"test data",
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        
        report = await store.generate_custody_report(item.id)
        
        assert report["evidence"]["filename"] == "screenshot.png"
        assert report["evidence"]["sha256_hash"] == item.sha256_hash
        assert report["evidence"]["source_agent"] == "recon-01"
    
    @pytest.mark.asyncio
    async def test_custody_report_includes_chain_integrity_verification(self):
        """Test custody report includes integrity verification."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        encryption_key = b"0" * 32
        mock_redis = AsyncMock()
        mock_custody_logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        report = await store.generate_custody_report(item.id)
        
        assert "integrity_verification" in report
        assert "all_signatures_valid" in report["integrity_verification"]
        assert "chain_complete" in report["integrity_verification"]
        assert "no_hash_changes" in report["integrity_verification"]
    
    @pytest.mark.asyncio
    async def test_custody_report_includes_signed_timestamps(self):
        """Test custody report includes cryptographic signatures."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        encryption_key = b"0" * 32
        mock_redis = AsyncMock()
        mock_custody_logger = CustodyAuditLogger("engagement-123", mock_redis)
        
        store = EvidenceStore(
            engagement_id="engagement-123",
            encryption_key=encryption_key,
            custody_logger=mock_custody_logger,
        )
        
        item = store.store_evidence(
            content=b"test data",
            filename="test.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        
        report = await store.generate_custody_report(item.id)
        
        # Each custody event should have signed_timestamp
        for event in report["custody_chain"]:
            assert "signed_timestamp" in event
            assert "timestamp" in event["signed_timestamp"]
            assert "signature" in event["signed_timestamp"]
