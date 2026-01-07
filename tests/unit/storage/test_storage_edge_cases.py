
import json
import pytest
from datetime import datetime
from pathlib import Path
import logging
import sys
from unittest.mock import Mock, patch, MagicMock

from cyberred.storage.checkpoint import (
    CheckpointJSONEncoder,
    CheckpointScopeChangedError,
    IncompatibleSchemaError,
    CheckpointManager,
    CheckpointIntegrityError
)

class TestCoverageGapFill:
    
    def test_json_encoder_types(self):
        """Cover CheckpointJSONEncoder types: set, bytes, datetime."""
        encoder = CheckpointJSONEncoder()
        dt = datetime(2025, 1, 1, 12, 0, 0)
        assert encoder.default(dt) == "2025-01-01T12:00:00"
        s = {1, 2, 3}
        serialized_set = encoder.default(s)
        assert isinstance(serialized_set, list)
        assert set(serialized_set) == s
        b = b"hello"
        assert encoder.default(b) == "68656c6c6f"
        with pytest.raises(TypeError):
            encoder.default(object())

    def test_exception_default_messages(self):
        """Cover exception __init__ with default messages."""
        e1 = CheckpointScopeChangedError("path", "expected", "actual")
        assert "Scope file has changed" in str(e1)
        e2 = IncompatibleSchemaError("path", "2.0.0", "1.0.0")
        assert "Checkpoint was created with schema version 2.0.0" in str(e2)

    @pytest.mark.asyncio
    async def test_save_removes_existing_temp_file(self, tmp_path: Path):
        """Cover save() line where temp file exists."""
        manager = CheckpointManager(tmp_path)
        engagement_id = "test-temp-exists"
        final_path = manager._get_checkpoint_path(engagement_id)
        temp_path = final_path.with_suffix(".sqlite.tmp")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.touch()
        await manager.save(engagement_id)
        assert final_path.exists()
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_load_invalid_version_string(self, tmp_path: Path):
        """Cover ValueError in version check."""
        with patch("cyberred.storage.checkpoint.log") as mock_log:
            manager = CheckpointManager(tmp_path)
            cp_path = await manager.save("test-bad-ver")
            
            import sqlite3
            conn = sqlite3.connect(cp_path)
            conn.execute("UPDATE metadata SET value = 'not.a.version' WHERE key = 'schema_version'")
            conn.commit()
            conn.close()
            
            await manager.load(cp_path)
            
            calls = [c for c in mock_log.warning.call_args_list if c[0][0] == "checkpoint_invalid_schema_version"]
            assert calls

    @pytest.mark.asyncio
    async def test_load_signature_mismatch(self, tmp_path: Path):
        """Cover signature mismatch error."""
        manager = CheckpointManager(tmp_path)
        cp_path = await manager.save("test-sig-fail")
        
        import sqlite3
        conn = sqlite3.connect(cp_path)
        conn.execute("UPDATE metadata SET value = 'tampered' WHERE key = 'engagement_id'")
        conn.commit()
        conn.close()
        
        with pytest.raises(CheckpointIntegrityError, match="signature mismatch"):
            await manager.load(cp_path)

    @pytest.mark.asyncio
    async def test_load_legacy_string_context(self, tmp_path: Path):
        """Cover decision_context as string handling."""
        manager = CheckpointManager(tmp_path)
        cp_path = await manager.save("test-legacy-ctx")
        
        import sqlite3
        conn = sqlite3.connect(cp_path)
        cursor = conn.execute("SELECT value FROM metadata WHERE key='signature'")
        original_sig = cursor.fetchone()[0]
        
        # INSERT value: {"key": "val"} (plain string)
        # In SQL: '{"key": "val"}'
        conn.execute("INSERT INTO agents (agent_id, engagement_id, agent_type, state_json, updated_at, decision_context) VALUES (?, ?, ?, ?, ?, ?)",
                     ('a1', 'test-legacy-ctx', 'recon', '{}', '2025-01-01', '{"key": "val"}'))
        conn.commit()
        conn.close()
        
        with patch.object(manager, '_calculate_content_signature', return_value=original_sig):
            data = await manager.load(cp_path)
            found_agent = next(a for a in data.agents if a.agent_id == 'a1')
            assert found_agent.decision_context == {"key": "val"}

    def test_verify_failure_missing_metadata(self, tmp_path: Path):
        """Cover verify() returning False on missing metadata."""
        manager = CheckpointManager(tmp_path)
        cp_path = tmp_path / "engagements" / "test-verify-fail" / "checkpoint.sqlite"
        cp_path.parent.mkdir(parents=True)
        import sqlite3
        conn = sqlite3.connect(cp_path)
        conn.execute("CREATE TABLE metadata (key text primary key, value text)")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('engagement_id', 'foo')")
        conn.commit()
        conn.close()
        assert manager.verify(cp_path) is False

    def test_env_config_loading(self):
        """Cover env.py config loading branch."""
        mock_alembic = MagicMock()
        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.config_file_name = "some_config.ini"
        mock_config.get_main_option.return_value = "sqlite:///:memory:"
        mock_context.config = mock_config
        # To avoid side-effects, we make it run offline mode logic which we patch
        mock_context.is_offline_mode.return_value = True 
        
        mock_alembic.context = mock_context
        
        with patch.dict(sys.modules, {'alembic': mock_alembic}):
            with patch('logging.config.fileConfig') as mock_fileConfig:
                # Patch run_migrations_offline to STOP it from doing anything
                # We need to target where it is DEFINED.
                # Since we are importing the module, we can't patch it before import
                # UNLESS we patch context.configure and run_migrations in the mock
                
                # If we import, it runs:
                # if context.is_offline_mode():
                #     run_migrations_offline()
                #       -> context.configure(...)
                #       -> with context.begin_transaction(): context.run_migrations()
                
                # So we just mock context.run_migrations and context.configure
                # which we already have via mock_context
                
                import importlib
                if "cyberred.storage.alembic.env" in sys.modules:
                    del sys.modules["cyberred.storage.alembic.env"]
                
                import cyberred.storage.alembic.env
                
                mock_fileConfig.assert_called_with("some_config.ini")
                assert mock_context.is_offline_mode.called

    def test_exception_custom_messages(self):
        """Cover exception __init__ with custom messages."""
        e1 = CheckpointScopeChangedError("path", "e", "a", message="Custom scope error")
        assert "Custom scope error" in str(e1)
        e2 = IncompatibleSchemaError("path", "2", "1", message="Custom version error")
        assert "Custom version error" in str(e2)

    @pytest.mark.asyncio
    async def test_save_error_after_conn_open(self, tmp_path: Path):
        """Cover save() cleanup when conn is open."""
        manager = CheckpointManager(tmp_path)
        
        # Mock _set_metadata to raise, causing cleanup with open conn
        with patch.object(manager, '_set_metadata', side_effect=RuntimeError("Fail mid-save")):
             with pytest.raises(RuntimeError):
                 await manager.save("test-mid-fail")
        
        # Temp file should be gone
        assert not any((tmp_path / "engagements" / "test-mid-fail").glob("*.tmp"))

    @pytest.mark.asyncio
    async def test_load_null_decision_context(self, tmp_path: Path):
        """Cover loading agent with NULL decision_context (non-string)."""
        manager = CheckpointManager(tmp_path)
        cp_path = await manager.save("test-null-ctx")
        
        import sqlite3
        conn = sqlite3.connect(cp_path)
        # Verify signature needs to be fixed if we mod DB? 
        # Actually save() creates a valid DB. We just need to inject a NULL context row
        # But inserting manual row invalidates signature.
        # So we mock signature verification again.
        
        conn.execute("INSERT INTO agents (agent_id, engagement_id, agent_type, state_json, updated_at, decision_context) VALUES (?, ?, ?, ?, ?, ?)",
                     ('a_null', 'test-null-ctx', 'recon', '{}', '2025-01-01', None))
        conn.commit()
        
        cursor = conn.execute("SELECT value FROM metadata WHERE key='signature'")
        original_sig = cursor.fetchone()[0]
        conn.close()
        
        with patch.object(manager, '_calculate_content_signature', return_value=original_sig):
            data = await manager.load(cp_path)
            agent = next(a for a in data.agents if a.agent_id == 'a_null')
            assert agent.decision_context is None
            
            # Also cover verify() branch for non-string context
            assert manager.verify(cp_path) is True


    def test_env_config_none(self):
        """Cover env.py where config_file_name is None."""
        mock_alembic = MagicMock()
        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.config_file_name = None # <--- The target
        mock_context.config = mock_config
        mock_context.is_offline_mode.return_value = False
        mock_alembic.context = mock_context
        
        with patch.dict(sys.modules, {'alembic': mock_alembic}):
            with patch('logging.config.fileConfig') as mock_fileConfig:
                # Patch sqlalchemy stuff to avoid side effects
                with patch('sqlalchemy.create_engine'), \
                     patch('sqlalchemy.event.listen'), \
                     patch('sqlalchemy.pool.NullPool'):
                    
                    import importlib
                    if "cyberred.storage.alembic.env" in sys.modules:
                        del sys.modules["cyberred.storage.alembic.env"]
                    
                    import cyberred.storage.alembic.env
                    
                    mock_fileConfig.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_cleanup_no_temp(self, tmp_path: Path):
        """Cover cleanup when temp file already gone."""
        manager = CheckpointManager(tmp_path)
        with patch.object(manager, '_create_connection', side_effect=RuntimeError):
             # Mock final_path.with_suffix().exists to return False
             # Complex because .exists() is on Path object.
             # Easier: Just ensure the file doesn't exist (it doesn't by default)
             # But save() creates it.
             # We need _initialize_schema (which creates file) to run, then _create_conn raises.
             # But we want .exists() to return False during cleanup.
             # So we must verify the file IS created, but then GONE when checked?
             # That implies a race.
             # We can mock Path.exists via side_effect.
             # [True (check old temp), False (during cleanup)]
             pass 
             # Simpler: If _initialize_schema fails, temp file might not exist.
             # If _initialize_schema raises, try-except catches.
             # if temp_path.exists() -> unlink.
             # If we fail BEFORE file creation?
             # manager._get_checkpoint_path doesn't create file.
             # unlink old temp -> (exists=False).
             # _initialize_schema -> Raises.
             # cleanup: exists() -> False.
        
        with patch.object(manager, '_initialize_schema', side_effect=RuntimeError):
            with pytest.raises(RuntimeError):
                await manager.save("test-no-temp")
            # Coverage: 438->440 (missing else)
            # If temp_path.exists() is False, we hit the else (implicit).

    @pytest.mark.asyncio
    async def test_load_missing_schema_version(self, tmp_path: Path):
        """Cover load with missing schema version."""
        manager = CheckpointManager(tmp_path)
        cp_path = await manager.save("test-no-ver")
        import sqlite3
        conn = sqlite3.connect(cp_path)
        conn.execute("UPDATE metadata SET value = '' WHERE key = 'schema_version'")
        conn.commit()
        conn.close()
        await manager.load(cp_path)
        # Should not raise, just skip version check

    @pytest.mark.asyncio
    async def test_load_scope_file_missing(self, tmp_path: Path):
        """Cover load with scope path that doesn't exist."""
        manager = CheckpointManager(tmp_path)
        # Save WITH scope hash so logic runs
        scope_file = tmp_path / "scope.txt"
        scope_file.write_text("content")
        cp_path = await manager.save("test-scope-missing", scope_path=scope_file)
        
        # Load with NON-EXISTENT scope path
        await manager.load(cp_path, scope_path=tmp_path / "ghost.txt")
        # Should skip verification logic without error

    @pytest.mark.asyncio
    async def test_load_scope_match(self, tmp_path: Path):
        """Cover load with matching scope."""
        manager = CheckpointManager(tmp_path)
        scope_file = tmp_path / "scope.txt"
        scope_file.write_text("content")
        cp_path = await manager.save("test-scope-match", scope_path=scope_file)
        
        # Load with same scope
        await manager.load(cp_path, scope_path=scope_file)
        # Passes

    @pytest.mark.asyncio
    async def test_verify_legacy_and_findings(self, tmp_path: Path):
        """Cover verify with legacy string context and findings."""
        manager = CheckpointManager(tmp_path)
        cp_path = await manager.save("test-verify-complex")
        
        import sqlite3
        conn = sqlite3.connect(cp_path)
        # Insert legacy agent
        conn.execute("""
            INSERT INTO agents (agent_id, engagement_id, agent_type, state_json, updated_at, decision_context)
            VALUES ('a1', 'test-verify-complex', 'recon', '{}', '2025-01-01', '{"key": "val"}')
        """)
        # Insert finding
        conn.execute("""
            INSERT INTO findings (finding_id, engagement_id, finding_json, agent_id, timestamp)
            VALUES ('f1', 'test-verify-complex', '{}', 'a1', '2025-01-01')
        """)

        # Fix signature
        # We can just update signature in metadata to match what we expect?
        # No, simpler to mock _calculate_content_signature in verify
        conn.commit()
        conn.close()
        
        # Mock calculate to return whatever is in DB
        # But wait, verify() reads signature from DB.
        # Then calls _calculate.
        # We need _calculate to return match.
        
        # First get the stored signature? No, it's invalid now.
        # We mock _get_metadata('signature') AND _calculate?
        # Or just mock _calculate to return "MATCH" and ensure DB has "MATCH".
        
        with patch.object(manager, '_calculate_content_signature', return_value="MATCH"):
             # We need to update DB signature to MATCH
             conn = sqlite3.connect(cp_path)
             conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('signature', 'MATCH')")
             conn.commit()
             conn.close()
             
             assert manager.verify(cp_path) is True

    def test_verify_crash(self, tmp_path: Path):
        """Cover verify exception handler."""
        manager = CheckpointManager(tmp_path)
        dummy = tmp_path / "crash.sqlite"
        dummy.touch()
        # Mock _create_connection to raise
        with patch.object(manager, '_create_connection', side_effect=OSError("Disk fail")):
            assert manager.verify(dummy) is False



