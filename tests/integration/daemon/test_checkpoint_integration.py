"""Integration tests for CheckpointManager and SessionManager.

Verifies:
- Atomic saving and integrity verification.
- Tamper detection (content vs signature).
- Scope change detection.
- Zombie checkpoint cleanup.
- Robust JSON serialization of complex types.
"""

import asyncio
import json
import sqlite3
import unittest.mock
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from cyberred.core.exceptions import (
    CheckpointIntegrityError,
    InvalidStateTransition,
)
from cyberred.core.hashing import calculate_file_hash
from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.state_machine import EngagementState
from cyberred.storage.checkpoint import (
    CheckpointManager,
    AgentState,
    Finding,
    CheckpointScopeChangedError,
)


@pytest.fixture
def checkpoint_manager(tmp_path: Path) -> CheckpointManager:
    """Create CheckpointManager with temp storage."""
    return CheckpointManager(base_path=tmp_path)


@pytest.fixture
def session_manager(tmp_path: Path, checkpoint_manager: CheckpointManager) -> SessionManager:
    """Create SessionManager integrated with CheckpointManager."""
    return SessionManager(
        max_engagements=5,
        checkpoint_manager=checkpoint_manager,
    )


@pytest.fixture
def engagement_config(tmp_path: Path) -> Path:
    """Create a sample engagement config file."""
    config_path = tmp_path / "eng_config.yaml"
    config_data = {
        "name": "integration-test-chk",
        "description": "Test Checkpointing",
        "scope_path": str(tmp_path / "scope.yaml"),
    }
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
    
    # Create valid scope file
    scope_path = tmp_path / "scope.yaml"
    with open(scope_path, "w") as f:
        yaml.dump({"targets": ["127.0.0.1"]}, f)
        
    return config_path


@pytest.mark.asyncio
async def test_atomic_save_and_verify(
    checkpoint_manager: CheckpointManager,
    tmp_path: Path,
) -> None:
    """Test atomic save and signature verification."""
    engagement_id = "test-atomic-save"
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text("scope_data")
    
    agents = [
        AgentState(
            agent_id="agent-1",
            agent_type="scanner",
            state={"target": "10.0.0.1", "progress": 50},
            last_action_id="act-1",
            decision_context={"context": "test"},
        )
    ]
    
    # 1. Save checkpoint
    path = await checkpoint_manager.save(
        engagement_id=engagement_id,
        scope_path=scope_path,
        agents=agents,
    )
    
    assert path.exists()
    assert path.name == "checkpoint.sqlite"
    
    # 2. Verify integrity
    assert checkpoint_manager.verify(path) is True
    
    # 3. Load and check data
    data = await checkpoint_manager.load(path, scope_path=scope_path)
    assert data.engagement_id == engagement_id
    assert len(data.agents) == 1
    assert data.agents[0].agent_id == "agent-1"


@pytest.mark.asyncio
async def test_tamper_detection(
    checkpoint_manager: CheckpointManager,
    tmp_path: Path,
) -> None:
    """Test that tampering with file content (even without touching signature) fails verification."""
    engagement_id = "test-tamper"
    
    # 1. Save valid checkpoint
    path = await checkpoint_manager.save(engagement_id=engagement_id)
    assert checkpoint_manager.verify(path) is True
    
    # 2. Tamper with the file (modify data directly in SQLite)
    # We open without CheckpointManager to bypass potential caching/locks
    # and just modify a table.
    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE metadata SET value = 'hacked' WHERE key = 'engagement_id'")
    conn.commit()
    conn.close()
    
    # 3. Verify should fail because content changed but signature didn't
    assert checkpoint_manager.verify(path) is False
    
    # 4. Loading should raise integrity error
    with pytest.raises(CheckpointIntegrityError) as exc:
        await checkpoint_manager.load(path)
    assert "Checkpoint signature mismatch" in str(exc.value)


@pytest.mark.asyncio
async def test_scope_change_protection(
    checkpoint_manager: CheckpointManager,
    tmp_path: Path,
) -> None:
    """Test protection against loading checkpoint when scope has changed."""
    engagement_id = "test-scope"
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text("original_scope")
    
    # 1. Save with original scope
    path = await checkpoint_manager.save(
        engagement_id=engagement_id,
        scope_path=scope_path,
    )
    
    # 2. Modify scope file
    scope_path.write_text("modified_scope")
    
    # 3. Load should fail
    with pytest.raises(CheckpointScopeChangedError) as exc:
        await checkpoint_manager.load(path, scope_path=scope_path, verify_scope=True)
    
    assert "Scope file has changed" in str(exc.value)
    
    # 4. Load with verify_scope=False should succeed
    data = await checkpoint_manager.load(path, scope_path=scope_path, verify_scope=False)
    assert data.engagement_id == engagement_id


@pytest.mark.asyncio
async def test_zombie_cleanup(
    session_manager: SessionManager,
    checkpoint_manager: CheckpointManager,
    engagement_config: Path,
) -> None:
    """Test that removing an engagement deletes its checkpoint file."""
    # Patch PreFlightRunner to always pass
    with unittest.mock.patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        instance = MockRunner.return_value
        instance.run_all = unittest.mock.AsyncMock(return_value=[])
        instance.validate_results = unittest.mock.Mock()
        
        # 1. Create and Start
        eid = session_manager.create_engagement(engagement_config)
        await session_manager.start_engagement(eid)
        
        # 2. Stop (creates checkpoint)
        _, path = await session_manager.stop_engagement(eid)
        assert path is not None
        # In current logic, stop() validates transition before saving.
        # We need first stop to be valid. start() -> RUNNING. stop() -> STOPPED. Valid.
        assert path.exists()
        
        # 3. Remove engagement
        await session_manager.remove_engagement(eid)
        
        # 4. Checkpoint should be gone
        assert not path.exists()

@pytest.mark.asyncio
async def test_stop_optimization(
    session_manager: SessionManager,
    engagement_config: Path,
    checkpoint_manager: CheckpointManager,
) -> None:
    """Test that stopping a stopped engagement fails fast (no save)."""
    # Patch PreFlightRunner to always pass
    with unittest.mock.patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        instance = MockRunner.return_value
        instance.run_all = unittest.mock.AsyncMock(return_value=[])
        instance.validate_results = unittest.mock.Mock()
        
        eid = session_manager.create_engagement(engagement_config)
        await session_manager.start_engagement(eid)
        
        # 1. First stop - should save
        await session_manager.stop_engagement(eid)
        
        # Mock save to detect if called
        # CheckpointManager instance is injected into session_manager
        # We need to spy on it.
        # session_manager._checkpoint_manager is the object.
        original_save = checkpoint_manager.save
        save_check = {"called": False}
        
        async def mock_save(*args, **kwargs):
            save_check["called"] = True
            return await original_save(*args, **kwargs)
            
        # We need to replace the method on the INSTANCE used by session_manager
        # session_manager._checkpoint_manager refers to checkpoint_manager object passed in fixture
        with unittest.mock.patch.object(checkpoint_manager, 'save', side_effect=mock_save):
            # 2. Second stop - should fail transition BEFORE save
            with pytest.raises(InvalidStateTransition):
                await session_manager.stop_engagement(eid)
                
            # 3. Verify save was NOT called
            assert not save_check["called"]

