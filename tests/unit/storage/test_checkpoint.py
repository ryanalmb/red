"""Unit Tests for storage/checkpoint.py module.

Tests for CheckpointManager, checkpoint save/load/verify operations,
and integrity verification.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from cyberred.storage.checkpoint import (
    CheckpointManager,
    CheckpointData,
    CheckpointScopeChangedError,
    AgentState,
    Finding,
    SCHEMA_VERSION,
)
from cyberred.core.exceptions import CheckpointIntegrityError


class TestCheckpointManager:
    """Tests for CheckpointManager class."""

    def test_init_creates_manager(self, tmp_path: Path):
        """Verify manager initializes with base path."""
        manager = CheckpointManager(base_path=tmp_path)
        assert manager.base_path == tmp_path

    def test_init_expands_user_path(self):
        """Verify ~ is expanded in base path."""
        manager = CheckpointManager(base_path=Path("~/.cyber-red"))
        assert "~" not in str(manager.base_path)

    def test_get_checkpoint_path(self, tmp_path: Path):
        """Verify checkpoint path structure."""
        manager = CheckpointManager(base_path=tmp_path)
        path = manager._get_checkpoint_path("test-engagement-123")
        expected = tmp_path / "engagements" / "test-engagement-123" / "checkpoint.sqlite"
        assert path == expected


class TestCheckpointSave:
    """Tests for CheckpointManager.save() method."""

    @pytest.mark.asyncio
    async def test_save_creates_checkpoint_file(self, tmp_path: Path):
        """Verify save creates checkpoint.sqlite file."""
        manager = CheckpointManager(base_path=tmp_path)
        
        checkpoint_path = await manager.save(engagement_id="test-123")
        
        assert checkpoint_path.exists()
        assert checkpoint_path.name == "checkpoint.sqlite"

    @pytest.mark.asyncio
    async def test_save_creates_directory_structure(self, tmp_path: Path):
        """Verify save creates engagement directory."""
        manager = CheckpointManager(base_path=tmp_path)
        
        await manager.save(engagement_id="my-engagement")
        
        engagement_dir = tmp_path / "engagements" / "my-engagement"
        assert engagement_dir.exists()
        assert engagement_dir.is_dir()

    @pytest.mark.asyncio
    async def test_save_stores_metadata(self, tmp_path: Path):
        """Verify metadata is stored correctly."""
        manager = CheckpointManager(base_path=tmp_path)
        
        checkpoint_path = await manager.save(engagement_id="test-meta")
        
        # Load and verify
        data = await manager.load(checkpoint_path, verify_scope=False)
        assert data.engagement_id == "test-meta"
        assert data.schema_version == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_save_with_agents(self, tmp_path: Path):
        """Verify agents are persisted."""
        manager = CheckpointManager(base_path=tmp_path)
        agents = [
            AgentState(
                agent_id="agent-1",
                agent_type="recon",
                state={"target": "192.168.1.1"},
            ),
            AgentState(
                agent_id="agent-2",
                agent_type="exploit",
                state={"payload": "shell"},
                last_action_id="action-99",
            ),
        ]
        
        checkpoint_path = await manager.save(
            engagement_id="test-agents",
            agents=agents,
        )
        
        data = await manager.load(checkpoint_path, verify_scope=False)
        assert len(data.agents) == 2
        assert data.agents[0].agent_id == "agent-1"
        assert data.agents[0].state == {"target": "192.168.1.1"}

    @pytest.mark.asyncio
    async def test_save_with_findings(self, tmp_path: Path):
        """Verify findings are persisted."""
        manager = CheckpointManager(base_path=tmp_path)
        findings = [
            Finding(
                finding_id="finding-1",
                data={"vulnerability": "SQLi", "severity": "HIGH"},
                agent_id="agent-1",
            ),
        ]
        
        checkpoint_path = await manager.save(
            engagement_id="test-findings",
            findings=findings,
        )
        
        data = await manager.load(checkpoint_path, verify_scope=False)
        assert len(data.findings) == 1
        assert data.findings[0].finding_id == "finding-1"
        assert data.findings[0].data["vulnerability"] == "SQLi"

    @pytest.mark.asyncio
    async def test_save_with_scope_hash(self, tmp_path: Path):
        """Verify scope file hash is calculated and stored."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Create scope file
        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text("targets:\n  - 192.168.1.0/24\n")
        
        checkpoint_path = await manager.save(
            engagement_id="test-scope",
            scope_path=scope_file,
        )
        
        data = await manager.load(checkpoint_path, verify_scope=False)
        assert data.scope_hash  # Non-empty hash
        assert len(data.scope_hash) == 64  # SHA-256 hex length

    @pytest.mark.asyncio
    async def test_save_overwrites_existing(self, tmp_path: Path):
        """Verify save overwrites existing checkpoint."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # First save
        await manager.save(
            engagement_id="test-overwrite",
            agents=[AgentState("a1", "recon", {"v": 1})],
        )
        
        # Second save with different data
        checkpoint_path = await manager.save(
            engagement_id="test-overwrite",
            agents=[AgentState("a2", "exploit", {"v": 2})],
        )
        
        data = await manager.load(checkpoint_path, verify_scope=False)
        assert len(data.agents) == 1
        assert data.agents[0].agent_id == "a2"


class TestCheckpointLoad:
    """Tests for CheckpointManager.load() method."""

    @pytest.mark.asyncio
    async def test_load_file_not_found(self, tmp_path: Path):
        """Verify FileNotFoundError for missing checkpoint."""
        manager = CheckpointManager(base_path=tmp_path)
        
        with pytest.raises(FileNotFoundError):
            await manager.load(tmp_path / "nonexistent.sqlite")

    @pytest.mark.asyncio
    async def test_load_verifies_scope_change(self, tmp_path: Path):
        """Verify scope change is detected and raises error."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Create scope file
        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text("targets:\n  - 192.168.1.0/24\n")
        
        # Save checkpoint with original scope
        checkpoint_path = await manager.save(
            engagement_id="test-scope-change",
            scope_path=scope_file,
        )
        
        # Modify scope file
        scope_file.write_text("targets:\n  - 10.0.0.0/8\n")
        
        # Load should raise scope changed error
        with pytest.raises(CheckpointScopeChangedError) as exc_info:
            await manager.load(checkpoint_path, scope_path=scope_file)
        
        assert "Scope file has changed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_skip_scope_verification(self, tmp_path: Path):
        """Verify scope verification can be skipped."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Create and save with scope
        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text("original")
        
        checkpoint_path = await manager.save(
            engagement_id="test-skip-scope",
            scope_path=scope_file,
        )
        
        # Change scope
        scope_file.write_text("modified")
        
        # Load with verify_scope=False should succeed
        data = await manager.load(
            checkpoint_path,
            scope_path=scope_file,
            verify_scope=False,
        )
        assert data.engagement_id == "test-skip-scope"


class TestCheckpointVerify:
    """Tests for CheckpointManager.verify() method."""

    @pytest.mark.asyncio
    async def test_verify_valid_checkpoint(self, tmp_path: Path):
        """Verify valid checkpoint returns True."""
        manager = CheckpointManager(base_path=tmp_path)
        
        checkpoint_path = await manager.save(engagement_id="test-verify")
        
        assert manager.verify(checkpoint_path) is True

    def test_verify_missing_file(self, tmp_path: Path):
        """Verify missing file returns False."""
        manager = CheckpointManager(base_path=tmp_path)
        
        assert manager.verify(tmp_path / "missing.sqlite") is False


class TestListCheckpoints:
    """Tests for CheckpointManager.list_checkpoints() method."""

    @pytest.mark.asyncio
    async def test_list_empty(self, tmp_path: Path):
        """Verify empty list when no checkpoints exist."""
        manager = CheckpointManager(base_path=tmp_path)
        
        checkpoints = manager.list_checkpoints()
        assert checkpoints == []

    @pytest.mark.asyncio
    async def test_list_multiple_checkpoints(self, tmp_path: Path):
        """Verify all checkpoints are listed."""
        manager = CheckpointManager(base_path=tmp_path)
        
        await manager.save(engagement_id="eng-1")
        await manager.save(engagement_id="eng-2")
        await manager.save(engagement_id="eng-3")
        
        checkpoints = manager.list_checkpoints()
        
        assert len(checkpoints) == 3
        engagement_ids = [eid for eid, _ in checkpoints]
        assert "eng-1" in engagement_ids
        assert "eng-2" in engagement_ids
        assert "eng-3" in engagement_ids


class TestVersionChecking:
    """Tests for schema version checking in load() (Task 10)."""

    @pytest.mark.asyncio
    async def test_load_current_version_succeeds(self, tmp_path: Path):
        """Verify loading checkpoint with current version succeeds."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Save creates checkpoint with current version
        checkpoint_path = await manager.save(engagement_id="test-version")
        
        # Load should succeed  
        data = await manager.load(checkpoint_path)
        assert data.schema_version == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_load_newer_version_raises_incompatible_error(self, tmp_path: Path):
        """Verify loading checkpoint with newer version raises IncompatibleSchemaError."""
        from cyberred.storage.checkpoint import IncompatibleSchemaError
        import sqlite3
        
        manager = CheckpointManager(base_path=tmp_path)
        
        # Save creates checkpoint with current version
        checkpoint_path = await manager.save(engagement_id="test-newer-version")
        
        # Manually update the schema version to a future version
        conn = sqlite3.connect(str(checkpoint_path))
        conn.execute("UPDATE metadata SET value = '99.0.0' WHERE key = 'schema_version'")
        conn.commit()
        conn.close()
        
        # Load should raise IncompatibleSchemaError
        with pytest.raises(IncompatibleSchemaError) as exc_info:
            await manager.load(checkpoint_path)
        
        assert exc_info.value.checkpoint_version == "99.0.0"
        assert exc_info.value.current_version == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_load_older_version_logs_upgrade_available(self, tmp_path: Path, caplog):
        """Verify loading checkpoint with older version logs upgrade info."""
        import sqlite3
        import logging
        
        manager = CheckpointManager(base_path=tmp_path)
        
        # Save creates checkpoint with current version
        checkpoint_path = await manager.save(engagement_id="test-older-version")
        
        # Manually update the schema version to an older version
        conn = sqlite3.connect(str(checkpoint_path))
        conn.execute("UPDATE metadata SET value = '1.0.0' WHERE key = 'schema_version'")
        conn.commit()
        conn.close()
        
        # Load should succeed (older versions are compatible)
        with caplog.at_level(logging.INFO):
            data = await manager.load(checkpoint_path)
        
        # Should have loaded successfully
        assert data.engagement_id == "test-older-version"
        # Schema version in data should reflect what's in the file
        assert data.schema_version == "1.0.0"


class TestCheckpointCleanup:
    """Tests for cleanup and deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self, tmp_path: Path):
        """Verify delete removes file and returns True."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Save then delete
        await manager.save(engagement_id="to-delete")
        assert (tmp_path / "engagements" / "to-delete" / "checkpoint.sqlite").exists()
        
        result = await manager.delete("to-delete")
        assert result is True
        assert not (tmp_path / "engagements" / "to-delete" / "checkpoint.sqlite").exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_path: Path):
        """Verify delete returns False for nonexistent."""
        manager = CheckpointManager(base_path=tmp_path)
        result = await manager.delete("ghost")
        assert result is False

    @pytest.mark.asyncio
    async def test_save_rollback_on_error(self, tmp_path: Path, monkeypatch):
        """Verify incomplete save is cleaned up on error."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Mock _create_connection to fail
        def mock_create(*args, **kwargs):
            raise RuntimeError("Connection failed")
            
        # We need to mock it on the instance or class. Since it's a method:
        monkeypatch.setattr(manager, "_create_connection", mock_create)
        
        with pytest.raises(RuntimeError, match="Connection failed"):
            await manager.save("fail-engagement")
            
        # Verify temp file is gone
        engagement_dir = tmp_path / "engagements" / "fail-engagement"
        if engagement_dir.exists():
            temp_files = list(engagement_dir.glob("*.tmp"))
            assert not temp_files, f"Temp files remained: {temp_files}"

    @pytest.mark.asyncio
    async def test_list_checkpoints_filtering(self, tmp_path: Path):
        """Verify list_checkpoints ignores invalid entries."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # 1. Valid engagement
        await manager.save(engagement_id="valid")
        
        # 2. File in engagements dir (not a directory)
        (tmp_path / "engagements" / "not-a-dir").touch()
        
        # 3. Directory without checkpoint file
        (tmp_path / "engagements" / "empty-dir").mkdir()
        
        checkpoints = manager.list_checkpoints()
        
        # Should only find the valid one
        assert len(checkpoints) == 1
        assert checkpoints[0][0] == "valid"
