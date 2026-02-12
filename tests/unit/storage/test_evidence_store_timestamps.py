"""Unit tests for evidence store timestamp signing integration (Story 13.10)."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from cyberred.storage.evidence_store import EvidenceStore, EvidenceType


class TestEvidenceStoreTimestampSigning:
    """Tests for timestamp signing in EvidenceStore."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test evidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def encryption_key(self):
        """32-byte encryption key for tests."""
        return b"0" * 32
    
    @pytest.fixture
    def evidence_store(self, temp_dir, encryption_key):
        """Create EvidenceStore instance for tests."""
        return EvidenceStore(
            engagement_id="test-engagement",
            encryption_key=encryption_key,
            base_path=temp_dir,
        )
    
    def test_store_evidence_includes_signed_timestamp(self, evidence_store):
        """Test that stored evidence includes signed_timestamp field."""
        content = b"test evidence content"
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Item should have signed_timestamp attribute
        assert hasattr(item, "signed_timestamp")
        assert item.signed_timestamp is not None
    
    def test_signed_timestamp_structure(self, evidence_store):
        """Test that signed_timestamp has timestamp, event_hash, signature fields."""
        content = b"test evidence content"
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        signed_ts = item.signed_timestamp
        assert isinstance(signed_ts, dict)
        assert "timestamp" in signed_ts
        assert "event_hash" in signed_ts
        assert "signature" in signed_ts
    
    def test_event_hash_is_sha256_of_content(self, evidence_store):
        """Test that event_hash in signed_timestamp is SHA-256 of file contents."""
        content = b"test evidence content"
        expected_hash = hashlib.sha256(content).hexdigest()
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        assert item.signed_timestamp["event_hash"] == expected_hash
    
    def test_signature_verification_on_evidence_retrieval(self, evidence_store, encryption_key):
        """Test that signature is verified when retrieving evidence."""
        content = b"test evidence content"
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Should have a method to verify timestamp signature
        # This will be implemented in GREEN phase
        assert hasattr(evidence_store, "verify_evidence_timestamp")
    
    def test_evidence_item_serialization_includes_signed_timestamp(self, evidence_store):
        """Test that EvidenceItem.to_dict() includes signed_timestamp."""
        content = b"test evidence content"
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        item_dict = item.to_dict()
        assert "signed_timestamp" in item_dict
        assert isinstance(item_dict["signed_timestamp"], dict)
    
    def test_evidence_item_deserialization_includes_signed_timestamp(self, evidence_store):
        """Test that EvidenceItem.from_dict() restores signed_timestamp."""
        content = b"test evidence content"
        
        item = evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Serialize and deserialize
        item_dict = item.to_dict()
        
        from cyberred.storage.evidence_store import EvidenceItem
        restored_item = EvidenceItem.from_dict(item_dict)
        
        assert hasattr(restored_item, "signed_timestamp")
        assert restored_item.signed_timestamp == item.signed_timestamp
    
    def test_different_content_produces_different_signatures(self, evidence_store):
        """Test that different evidence produces different signatures."""
        item1 = evidence_store.store_evidence(
            content=b"content1",
            filename="test1.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        item2 = evidence_store.store_evidence(
            content=b"content2",
            filename="test2.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        assert item1.signed_timestamp["signature"] != item2.signed_timestamp["signature"]
    
    def test_manifest_includes_signed_timestamps(self, evidence_store):
        """Test that manifest.json includes signed_timestamp for each item."""
        content = b"test evidence content"
        
        evidence_store.store_evidence(
            content=content,
            filename="test.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        
        # Load manifest
        manifest_path = evidence_store._manifest_path
        import json
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert len(manifest["evidence"]) == 1
        assert "signed_timestamp" in manifest["evidence"][0]
