"""Unit tests for CheckpointData config storage - Story 13.3 AC#6.

Tests for extending CheckpointData to include engagement config:
- Config field in CheckpointData dataclass
- Config serialization in save()
- Config deserialization in load()
- Config included in signature calculation

TDD RED PHASE: All tests should FAIL until implementation exists.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cyberred.storage.checkpoint import (
    CheckpointManager,
    CheckpointData,
    AgentState,
    Finding,
)


class TestCheckpointDataConfigField:
    """Tests for config field in CheckpointData."""

    def test_checkpoint_data_has_config_field(self) -> None:
        """
        GIVEN CheckpointData dataclass
        WHEN instantiated
        THEN config field exists with default empty dict
        """
        data = CheckpointData(
            engagement_id="eng-1",
            scope_hash="abc123",
            created_at=datetime.now(timezone.utc),
            schema_version="2.0.0",
        )
        
        assert hasattr(data, "config")
        assert data.config == {}

    def test_checkpoint_data_accepts_config_dict(self) -> None:
        """
        GIVEN CheckpointData dataclass
        WHEN instantiated with config dict
        THEN config is stored correctly
        """
        config = {
            "engagement_name": "Test Engagement",
            "roe_hash": "def456",
            "models_config": {"provider": "nvidia-nim"},
        }
        
        data = CheckpointData(
            engagement_id="eng-1",
            scope_hash="abc123",
            created_at=datetime.now(timezone.utc),
            schema_version="2.0.0",
            config=config,
        )
        
        assert data.config == config
        assert data.config["engagement_name"] == "Test Engagement"


class TestCheckpointManagerSaveConfig:
    """Tests for saving config in checkpoints."""

    @pytest.mark.asyncio
    async def test_save_accepts_config_parameter(self) -> None:
        """
        GIVEN CheckpointManager
        WHEN save() is called with config parameter
        THEN no error is raised
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "engagement_name": "Test",
                "roe_hash": "abc123",
            }
            
            # Should not raise - config parameter accepted
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            assert path.exists()

    @pytest.mark.asyncio
    async def test_save_stores_config_in_database(self) -> None:
        """
        GIVEN CheckpointManager
        WHEN save() is called with config
        THEN config is stored in SQLite database
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "engagement_name": "Test Engagement",
                "roe_hash": "def456",
                "models_config": {"provider": "nvidia-nim"},
            }
            
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            # Verify config is stored (check metadata table)
            import sqlite3
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT value FROM metadata WHERE key = 'config'"
            )
            row = cursor.fetchone()
            conn.close()
            
            assert row is not None
            stored_config = json.loads(row["value"])
            assert stored_config["engagement_name"] == "Test Engagement"


class TestCheckpointManagerLoadConfig:
    """Tests for loading config from checkpoints."""

    @pytest.mark.asyncio
    async def test_load_returns_checkpoint_with_config(self) -> None:
        """
        GIVEN a checkpoint with config stored
        WHEN load() is called
        THEN CheckpointData includes config field
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "engagement_name": "Test Engagement",
                "roe_hash": "def456",
            }
            
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            assert data.config is not None
            assert data.config["engagement_name"] == "Test Engagement"
            assert data.config["roe_hash"] == "def456"

    @pytest.mark.asyncio
    async def test_load_returns_empty_config_if_not_stored(self) -> None:
        """
        GIVEN a checkpoint without config (legacy)
        WHEN load() is called
        THEN CheckpointData has empty config dict
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Save without config (existing behavior)
            path = await manager.save(engagement_id="eng-1")
            
            data = await manager.load(path, verify_scope=False)
            
            # Should have empty dict, not None
            assert data.config == {}


class TestCheckpointConfigSerialization:
    """Tests for config JSON serialization edge cases."""

    @pytest.mark.asyncio
    async def test_config_handles_datetime_serialization(self) -> None:
        """
        GIVEN config contains datetime objects
        WHEN save() and load() are called
        THEN datetime is serialized/deserialized correctly
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            now = datetime.now(timezone.utc)
            config = {
                "created_at": now,
                "updated_at": now,
            }
            
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            # Datetime should be stored as ISO string
            assert "created_at" in data.config
            # Accept either datetime object or ISO string
            created = data.config["created_at"]
            if isinstance(created, str):
                assert "T" in created  # ISO format
            else:
                assert isinstance(created, datetime)

    @pytest.mark.asyncio
    async def test_config_handles_set_serialization(self) -> None:
        """
        GIVEN config contains set objects
        WHEN save() and load() are called
        THEN set is serialized as list
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "allowed_ports": {22, 80, 443},
            }
            
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            # Set should be converted to list
            assert "allowed_ports" in data.config
            ports = data.config["allowed_ports"]
            assert isinstance(ports, list)
            assert set(ports) == {22, 80, 443}

    @pytest.mark.asyncio
    async def test_config_handles_bytes_serialization(self) -> None:
        """
        GIVEN config contains bytes objects
        WHEN save() and load() are called
        THEN bytes is serialized as hex string
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "key_hash": b"\xde\xad\xbe\xef",
            }
            
            path = await manager.save(
                engagement_id="eng-1",
                config=config,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            assert "key_hash" in data.config
            assert data.config["key_hash"] == "deadbeef"


class TestCheckpointConfigSignature:
    """Tests for config included in signature calculation."""

    @pytest.mark.asyncio
    async def test_config_change_changes_signature(self) -> None:
        """
        GIVEN two checkpoints with different configs
        WHEN saved
        THEN they have different signatures
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Save first checkpoint
            path1 = await manager.save(
                engagement_id="eng-1",
                config={"version": 1},
            )
            
            # Get signature 1
            import sqlite3
            conn = sqlite3.connect(str(path1))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'signature'")
            sig1 = cursor.fetchone()["value"]
            conn.close()
            
            # Save second checkpoint with different config
            path2 = await manager.save(
                engagement_id="eng-2",
                config={"version": 2},
            )
            
            # Get signature 2
            conn = sqlite3.connect(str(path2))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'signature'")
            sig2 = cursor.fetchone()["value"]
            conn.close()
            
            # Signatures should differ (different engagement_id and config)
            assert sig1 != sig2

    @pytest.mark.asyncio
    async def test_verify_detects_config_tampering(self) -> None:
        """
        GIVEN a checkpoint with config
        WHEN config is manually modified in database
        THEN verify() returns False
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            path = await manager.save(
                engagement_id="eng-1",
                config={"secret": "original"},
            )
            
            # Verify passes before tampering
            assert manager.verify(path) is True
            
            # Tamper with config
            import sqlite3
            conn = sqlite3.connect(str(path))
            conn.execute(
                "UPDATE metadata SET value = ? WHERE key = 'config'",
                (json.dumps({"secret": "tampered"}),)
            )
            conn.commit()
            conn.close()
            
            # Verify should now fail
            assert manager.verify(path) is False


class TestCheckpointConfigContent:
    """Tests for expected config content."""

    @pytest.mark.asyncio
    async def test_config_includes_engagement_settings(self) -> None:
        """
        GIVEN a typical engagement config
        WHEN saved
        THEN all expected fields are preserved
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            config = {
                "engagement_name": "Acme Corp Assessment",
                "roe_hash": "abc123def456",
                "models_config": {
                    "strategist": "deepseek-r1",
                    "analyst": "kimi-k2",
                    "creative": "minimax-m2",
                },
                "scope_config": {
                    "include_patterns": ["*.acme.com"],
                    "exclude_patterns": ["prod.acme.com"],
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            path = await manager.save(
                engagement_id="eng-acme",
                config=config,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            assert data.config["engagement_name"] == "Acme Corp Assessment"
            assert data.config["roe_hash"] == "abc123def456"
            assert data.config["models_config"]["strategist"] == "deepseek-r1"
            assert "*.acme.com" in data.config["scope_config"]["include_patterns"]
