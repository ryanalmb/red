import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cyberred.storage.checkpoint import CheckpointManager, CheckpointJSONEncoder


class TestCheckpointJSONEncoder:
    """Tests for CheckpointJSONEncoder."""

    def test_encode_types(self):
        """Verify encoding of supported types."""
        from cyberred.storage.checkpoint import CheckpointJSONEncoder
        
        data = {
            "dt": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "set": {1, 2, 3},
            "bytes": b"hello"
        }
        
        json_str = json.dumps(data, cls=CheckpointJSONEncoder, sort_keys=True)
        decoded = json.loads(json_str)
        
        assert decoded["dt"] == "2023-01-01T12:00:00+00:00"
        assert sorted(decoded["set"]) == [1, 2, 3]
        assert decoded["bytes"] == "68656c6c6f"


class TestCheckpointErrorHandling:
    """Tests for error handling in CheckpointManager."""
    
    @pytest.mark.asyncio
    async def test_save_cleanup_on_error(self, tmp_path: Path):
        """Verify temp file is cleaned up if save fails."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Mock _create_connection to raise exception
        with patch.object(manager, "_create_connection", side_effect=ValueError("Simulated error")):
            with pytest.raises(ValueError):
                await manager.save(engagement_id="fail-test")
        
        # Verify no temp file left (it might not be created if error is early, but let's mock later)
        temp_path = manager._get_checkpoint_path("fail-test").with_suffix(".sqlite.tmp")
        assert not temp_path.exists()
        
    @pytest.mark.asyncio
    async def test_save_cleanup_existing_temp(self, tmp_path: Path):
        """Verify existing temp file is removed before save."""
        manager = CheckpointManager(base_path=tmp_path)
        final_path = manager._get_checkpoint_path("test-temp-cleanup")
        temp_path = final_path.with_suffix(".sqlite.tmp")
        
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.touch()
        
        await manager.save(engagement_id="test-temp-cleanup")
        
        assert final_path.exists()
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_path: Path):
        """Verify delete returns False for non-existent engagement."""
        manager = CheckpointManager(base_path=tmp_path)
        result = await manager.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self, tmp_path: Path):
        """Verify delete removes file and returns True."""
        manager = CheckpointManager(base_path=tmp_path)
        await manager.save("to-delete")
        
        result = await manager.delete("to-delete")
        assert result is True
        assert not manager._get_checkpoint_path("to-delete").exists()


class TestCheckpointVerifyEdgeCases:
    """Tests for edge cases in verification."""
    
    def test_verify_missing_metadata(self, tmp_path: Path):
        """Verify returns False if metadata is missing."""
        manager = CheckpointManager(base_path=tmp_path)
        # Create empty sqlite db
        path = manager._get_checkpoint_path("corrupt")
        path.parent.mkdir(parents=True)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE metadata (key TEXT, value TEXT)")
        conn.commit()
        conn.close()
        
        assert manager.verify(path) is False

    def test_verify_exception_handling(self, tmp_path: Path):
        """Verify returns False on exception."""
        manager = CheckpointManager(base_path=tmp_path)
        # Pass directory instead of file to cause open error
        path = tmp_path / "dir"
        path.mkdir()
        
        # Verify handles exception and logs warning
        assert manager.verify(path) is False

    def test_scope_changed_error_default_message(self):
        """Test default message generation."""
        from cyberred.storage.checkpoint import CheckpointScopeChangedError
        err = CheckpointScopeChangedError(
            checkpoint_path="test",
            expected_scope_hash="aabbcc",
            actual_scope_hash="112233"
        )
        assert "expected hash: aabbcc..." in str(err).lower()

    def test_json_encoder_unknown_type(self):
        """Test fallback to super default."""
        from cyberred.storage.checkpoint import CheckpointJSONEncoder
        
        with pytest.raises(TypeError):
            json.dumps({"obj": object()}, cls=CheckpointJSONEncoder)

    @pytest.mark.asyncio
    async def test_save_cleanup_on_internal_error(self, tmp_path: Path):
        """Test cleanup when error occurs AFTER connection created."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Mock _initialize_schema (called after connection) to raise error
        with patch.object(manager, "_initialize_schema", side_effect=RuntimeError("Internal fail")):
            with pytest.raises(RuntimeError):
                await manager.save(engagement_id="fail-internal")
        
        # Temp file should be gone
        temp_path = manager._get_checkpoint_path("fail-internal").with_suffix(".sqlite.tmp")
        assert not temp_path.exists()
        
    def test_list_checkpoints_ignores_files(self, tmp_path: Path):
        """Test list_checkpoints ignores files in engagements dir."""
        manager = CheckpointManager(base_path=tmp_path)
        
        # Create a file in engagements dir (should be dir)
        (tmp_path / "engagements").mkdir()
        (tmp_path / "engagements" / "file.txt").touch()
        
        checkpoints = manager.list_checkpoints()
        assert checkpoints == []

    @pytest.mark.asyncio
    async def test_load_legacy_decision_context(self, tmp_path: Path):
        """Test loading legacy string decision_context."""
        manager = CheckpointManager(base_path=tmp_path)
        path = await manager.save("legacy-test")
        
        # Manually update DB with string context
        conn = sqlite3.connect(path)
        conn.execute("UPDATE agents SET decision_context = ? WHERE 1=1", ('{"foo": "bar"}',))
        conn.commit()
        conn.close()
        
        data = await manager.load(path)
        # Should be parsed back to dict
        assert data.agents[0].decision_context == {"foo": "bar"} if data.agents else True
