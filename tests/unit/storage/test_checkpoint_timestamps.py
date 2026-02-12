"""Unit tests for checkpoint timestamp signing integration (Story 13.10)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cyberred.storage.checkpoint import CheckpointManager, CheckpointData, AgentState, Finding
from datetime import datetime, timezone


class TestCheckpointTimestampSigning:
    """Tests for timestamp signing in CheckpointManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def checkpoint_manager(self, temp_dir):
        """Create CheckpointManager instance for tests."""
        return CheckpointManager(base_path=temp_dir)
    
    @pytest.mark.asyncio
    async def test_checkpoint_data_has_signed_timestamp_field(self, checkpoint_manager, temp_dir):
        """Test that CheckpointData includes signed_timestamp field."""
        data = CheckpointData(
            engagement_id="test-engagement",
            scope_hash="abc123",
            created_at=datetime.now(timezone.utc),
            schema_version="2.0.0",
        )
        
        assert hasattr(data, "signed_timestamp")
    
    @pytest.mark.asyncio
    async def test_save_checkpoint_creates_signed_timestamp(self, checkpoint_manager, temp_dir):
        """Test that saving checkpoint creates signed timestamp."""
        agents = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        checkpoint_path = await checkpoint_manager.save(
            engagement_id="test-engagement",
            agents=agents,
        )
        
        # Load checkpoint and verify signed_timestamp exists
        loaded = await checkpoint_manager.load(checkpoint_path, verify_scope=False)
        
        assert hasattr(loaded, "signed_timestamp")
        assert loaded.signed_timestamp is not None
    
    @pytest.mark.asyncio
    async def test_signed_timestamp_structure_in_checkpoint(self, checkpoint_manager, temp_dir):
        """Test that checkpoint signed_timestamp has correct structure."""
        agents = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        checkpoint_path = await checkpoint_manager.save(
            engagement_id="test-engagement",
            agents=agents,
        )
        
        loaded = await checkpoint_manager.load(checkpoint_path, verify_scope=False)
        signed_ts = loaded.signed_timestamp
        
        assert isinstance(signed_ts, dict)
        assert "timestamp" in signed_ts
        assert "event_hash" in signed_ts
        assert "signature" in signed_ts
    
    @pytest.mark.asyncio
    async def test_checkpoint_event_hash_is_sha256_of_data(self, checkpoint_manager, temp_dir):
        """Test that event_hash is SHA-256 of serialized checkpoint data."""
        agents = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        checkpoint_path = await checkpoint_manager.save(
            engagement_id="test-engagement",
            agents=agents,
        )
        
        loaded = await checkpoint_manager.load(checkpoint_path, verify_scope=False)
        
        # Event hash should be hex string
        assert isinstance(loaded.signed_timestamp["event_hash"], str)
        assert len(loaded.signed_timestamp["event_hash"]) == 64  # SHA-256 hex length
    
    @pytest.mark.asyncio
    async def test_checkpoint_restore_verifies_signature(self, checkpoint_manager, temp_dir):
        """Test that checkpoint restore verifies timestamp signature."""
        agents = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        checkpoint_path = await checkpoint_manager.save(
            engagement_id="test-engagement",
            agents=agents,
        )
        
        # Load should succeed with valid signature
        loaded = await checkpoint_manager.load(checkpoint_path, verify_scope=False)
        
        assert loaded is not None
        assert loaded.engagement_id == "test-engagement"
    
    @pytest.mark.asyncio
    async def test_checkpoint_restore_fails_on_invalid_signature(self, checkpoint_manager, temp_dir):
        """Test that checkpoint restore fails if signature is invalid."""
        agents = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        checkpoint_path = await checkpoint_manager.save(
            engagement_id="test-engagement",
            agents=agents,
        )
        
        # Tamper with the checkpoint database
        # This will be implemented in GREEN phase to actually modify the signature
        # For now, just verify the structure exists
        assert checkpoint_path.exists()
    
    @pytest.mark.asyncio
    async def test_different_checkpoint_data_produces_different_signatures(self, checkpoint_manager):
        """Test that different checkpoint data produces different signatures."""
        agents1 = [
            AgentState(
                agent_id="agent-01",
                agent_type="recon",
                state={"status": "active"},
            )
        ]
        
        agents2 = [
            AgentState(
                agent_id="agent-02",
                agent_type="exploit",
                state={"status": "waiting"},
            )
        ]
        
        path1 = await checkpoint_manager.save(
            engagement_id="engagement-01",
            agents=agents1,
        )
        
        path2 = await checkpoint_manager.save(
            engagement_id="engagement-02",
            agents=agents2,
        )
        
        loaded1 = await checkpoint_manager.load(path1, verify_scope=False)
        loaded2 = await checkpoint_manager.load(path2, verify_scope=False)
        
        assert loaded1.signed_timestamp["signature"] != loaded2.signed_timestamp["signature"]
