"""Integration tests for end-to-end custody chain tracking.

Story 13.11: Evidence Chain of Custody

Integration tests with real Redis for custody chain tracking.
These tests should FAIL until implementation is complete (RED phase).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pytest
import tempfile
import zipfile
from pathlib import Path

from cyberred.storage.evidence_store import EvidenceStore, EvidenceType


@pytest.mark.integration
class TestCustodyChainEndToEnd:
    """Test complete custody chain lifecycle.
    
    Task 6: Write Failing Integration Tests for End-to-End Custody Flow (AC: all)
    """
    
    @pytest.fixture
    async def redis_client(self, redis_container):
        """Get real Redis client from container fixture."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        
        config = RedisConfig(
            host=redis_container.get_container_host_ip(),
            port=int(redis_container.get_exposed_port(6379)),
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client = RedisClient(config, engagement_id="custody-test")
        await client.connect()
        yield client
        await client.close()
    
    @pytest.mark.asyncio
    async def test_full_custody_lifecycle_store_access_export(self, redis_client):
        """Test full lifecycle: store → access → export with custody tracking."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-custody-1"
        encryption_key = b"0" * 32
        
        # Create custody logger with real Redis
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        # Create evidence store
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            # 1. Store evidence (CREATE event)
            content = b"sensitive data from target"
            item = store.store_evidence(
                content=content,
                filename="credentials.txt",
                source_agent="recon-42",
                evidence_type=EvidenceType.LOOT,
                operator="system",
            )
            
            # Wait for async custody logging
            await asyncio.sleep(0.1)
            
            # 2. Access evidence (ACCESS event)
            retrieved = store.get_evidence(
                evidence_id=item.id,
                operator="root",
                access_reason="forensic analysis",
            )
            assert retrieved == content
            
            # Wait for async custody logging
            await asyncio.sleep(0.1)
            
            # 3. Export evidence (EXPORT event)
            export_path = Path(tmpdir) / "export.zip"
            await store.export_evidence_with_custody(
                evidence_ids=[item.id],
                destination=export_path,
                operator="root",
            )
            
            # Wait for async custody logging
            await asyncio.sleep(0.1)
            
            # 4. Verify custody chain
            chain = await custody_logger.get_custody_chain(item.id)
            
            # Should have: CREATE, ACCESS (manual), ACCESS (from export), EXPORT
            assert len(chain) >= 3
            assert chain[0].action == "CREATE"
            assert chain[0].operator == "system"
            # Find the manual ACCESS event
            access_events = [e for e in chain if e.action == "ACCESS"]
            assert len(access_events) >= 1
            assert any(e.operator == "root" for e in access_events)
            # Find the EXPORT event
            export_events = [e for e in chain if e.action == "EXPORT"]
            assert len(export_events) == 1
            assert export_events[0].operator == "root"
    
    @pytest.mark.asyncio
    async def test_custody_chain_reconstruction_across_operators(self, redis_client):
        """Test custody chain tracks multiple operators."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-custody-2"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            # Create evidence
            item = store.store_evidence(
                content=b"test data",
                filename="test.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="operator1",
            )
            
            await asyncio.sleep(0.1)
            
            # Access by operator2
            store.get_evidence(
                evidence_id=item.id,
                operator="operator2",
                access_reason="review",
            )
            
            await asyncio.sleep(0.1)
            
            # Access by operator3
            store.get_evidence(
                evidence_id=item.id,
                operator="operator3",
                access_reason="audit",
            )
            
            await asyncio.sleep(0.1)
            
            # Verify chain has all operators
            chain = await custody_logger.get_custody_chain(item.id)
            
            operators = [event.operator for event in chain]
            assert "operator1" in operators
            assert "operator2" in operators
            assert "operator3" in operators
    
    @pytest.mark.asyncio
    async def test_custody_events_survive_system_restart(self, redis_client):
        """Test custody events persist in Redis across restarts."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-custody-3"
        encryption_key = b"0" * 32
        
        # First instance
        custody_logger_1 = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store_1 = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger_1,
            )
            
            item = store_1.store_evidence(
                content=b"test data",
                filename="test.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            evidence_id = item.id
            
            # Simulate restart - new logger instance
            custody_logger_2 = CustodyAuditLogger(engagement_id, redis_client)
            
            # Retrieve custody chain with new instance
            chain = await custody_logger_2.get_custody_chain(evidence_id)
            
            assert len(chain) >= 1
            assert chain[0].action == "CREATE"
    
    @pytest.mark.asyncio
    async def test_custody_verification_with_signed_timestamps(self, redis_client):
        """Test custody verification using signed timestamps."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        from cyberred.core.time import verify_event_timestamp
        
        engagement_id = "test-engagement-custody-4"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            item = store.store_evidence(
                content=b"sensitive data",
                filename="secrets.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOOT,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            # Get custody chain
            chain = await custody_logger.get_custody_chain(item.id)
            
            # Verify each signed timestamp
            # Note: custody logger uses its own signing key, not the encryption key
            for event in chain:
                assert event.signed_timestamp is not None
                # Verify with custody logger's signing key (derived from engagement_id)
                from cyberred.core.keystore import derive_key
                custody_signing_key = derive_key(engagement_id, salt=b"hmac-sha256")
                is_valid = verify_event_timestamp(
                    event.signed_timestamp,
                    custody_signing_key,
                )
                assert is_valid is True


@pytest.mark.integration
class TestEvidenceExportWithCustody:
    """Test evidence export includes custody information.
    
    Task 5: Write Failing Integration Tests for Export with Custody (AC: 1)
    """
    
    @pytest.fixture
    async def redis_client(self, redis_container):
        """Get real Redis client from container fixture."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        
        config = RedisConfig(
            host=redis_container.get_container_host_ip(),
            port=int(redis_container.get_exposed_port(6379)),
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client = RedisClient(config, engagement_id="custody-export-test")
        await client.connect()
        yield client
        await client.close()
    
    @pytest.mark.asyncio
    async def test_export_includes_chain_of_custody_json(self, redis_client):
        """Test evidence export includes chain_of_custody.json."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-export-1"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            # Store evidence
            item = store.store_evidence(
                content=b"test data",
                filename="test.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            # Export with custody
            export_path = Path(tmpdir) / "export.zip"
            await store.export_evidence_with_custody(
                evidence_ids=[item.id],
                destination=export_path,
                operator="root",
            )
            
            # Verify export contains custody report
            assert export_path.exists()
            
            with zipfile.ZipFile(export_path, 'r') as zf:
                files = zf.namelist()
                assert any("chain_of_custody" in f for f in files)
    
    @pytest.mark.asyncio
    async def test_zip_export_contains_custody_report(self, redis_client):
        """Test ZIP archive contains custody report."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-export-2"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            item = store.store_evidence(
                content=b"evidence content",
                filename="evidence.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            export_path = Path(tmpdir) / "export.zip"
            await store.export_evidence_with_custody(
                evidence_ids=[item.id],
                destination=export_path,
                operator="root",
            )
            
            # Extract and verify custody report
            with zipfile.ZipFile(export_path, 'r') as zf:
                custody_files = [f for f in zf.namelist() if "chain_of_custody" in f]
                assert len(custody_files) > 0
                
                custody_json = zf.read(custody_files[0])
                custody_data = json.loads(custody_json)
                
                assert "evidence" in custody_data
                assert "custody_chain" in custody_data
    
    @pytest.mark.asyncio
    async def test_export_event_logged_to_custody_chain(self, redis_client):
        """Test export operation logs EXPORT event to custody chain."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-export-3"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            item = store.store_evidence(
                content=b"test data",
                filename="test.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            # Get chain before export
            chain_before = await custody_logger.get_custody_chain(item.id)
            before_count = len(chain_before)
            
            # Export
            export_path = Path(tmpdir) / "export.zip"
            await store.export_evidence_with_custody(
                evidence_ids=[item.id],
                destination=export_path,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            # Get chain after export
            chain_after = await custody_logger.get_custody_chain(item.id)
            
            # Export creates an ACCESS event (for get_evidence) and an EXPORT event
            assert len(chain_after) >= before_count + 1
            export_events = [e for e in chain_after if e.action == "EXPORT"]
            assert len(export_events) >= 1
            assert export_events[-1].action == "EXPORT"
    
    @pytest.mark.asyncio
    async def test_multi_evidence_export_includes_all_custody_chains(self, redis_client):
        """Test multi-evidence export includes custody chains for all items."""
        
        
        from cyberred.core.audit import CustodyAuditLogger
        
        engagement_id = "test-engagement-export-4"
        encryption_key = b"0" * 32
        
        custody_logger = CustodyAuditLogger(engagement_id, redis_client)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=Path(tmpdir),
                custody_logger=custody_logger,
            )
            
            # Store multiple evidence items
            item1 = store.store_evidence(
                content=b"data 1",
                filename="file1.txt",
                source_agent="recon-01",
                evidence_type=EvidenceType.LOG,
                operator="root",
            )
            
            item2 = store.store_evidence(
                content=b"data 2",
                filename="file2.txt",
                source_agent="recon-02",
                evidence_type=EvidenceType.LOOT,
                operator="root",
            )
            
            await asyncio.sleep(0.1)
            
            # Export both
            export_path = Path(tmpdir) / "export.zip"
            await store.export_evidence_with_custody(
                evidence_ids=[item1.id, item2.id],
                destination=export_path,
                operator="root",
            )
            
            # Verify both custody chains in export
            with zipfile.ZipFile(export_path, 'r') as zf:
                custody_files = [f for f in zf.namelist() if "chain_of_custody" in f]
                
                # Should have custody data for both items
                assert len(custody_files) >= 1
