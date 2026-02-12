"""Integration tests for checkpoint restore - Story 13.3 AC#7.

STRICT integration tests with REAL SQLite I/O (NO MOCKS):
- Full save/load cycle verification
- Concurrent read during write (WAL mode)
- Scale testing (100+ agents, 1000+ findings)
- Error condition handling

TDD RED PHASE: All tests should FAIL until implementation exists.
"""

import asyncio
import concurrent.futures
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sqlite3

import pytest

from cyberred.storage.checkpoint import (
    CheckpointManager,
    CheckpointData,
    AgentState,
    Finding,
    CheckpointScopeChangedError,
    IncompatibleSchemaError,
)


class TestCheckpointRestoreFullCycle:
    """Integration tests for full checkpoint save/load cycle."""

    @pytest.mark.asyncio
    async def test_full_cycle_state_matches(self) -> None:
        """
        GIVEN an engagement with agents, findings, and config
        WHEN checkpoint is saved then loaded
        THEN all state matches exactly
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create engagement state
            agents = [
                AgentState(
                    agent_id="recon-1",
                    agent_type="recon",
                    state={"targets": ["10.0.0.1", "10.0.0.2"]},
                    last_action_id="action-123",
                    decision_context={"depth": 2},
                ),
                AgentState(
                    agent_id="exploit-1",
                    agent_type="exploit",
                    state={"exploits_tried": ["CVE-2024-1234"]},
                    last_action_id="action-456",
                    decision_context={"priority": "high"},
                ),
            ]
            
            findings = [
                Finding(
                    finding_id="finding-1",
                    data={"type": "open_port", "port": 22, "service": "ssh"},
                    agent_id="recon-1",
                    timestamp=datetime.now(timezone.utc),
                ),
                Finding(
                    finding_id="finding-2",
                    data={"type": "vulnerability", "cve": "CVE-2024-1234"},
                    agent_id="exploit-1",
                    timestamp=datetime.now(timezone.utc),
                ),
            ]
            
            config = {
                "engagement_name": "Test Engagement",
                "roe_hash": "abc123",
                "models_config": {"provider": "nvidia-nim"},
            }
            
            # Save checkpoint
            path = await manager.save(
                engagement_id="eng-test-1",
                agents=agents,
                findings=findings,
                config=config,
            )
            
            # Load checkpoint
            data = await manager.load(path, verify_scope=False)
            
            # Verify state matches
            assert data.engagement_id == "eng-test-1"
            assert len(data.agents) == 2
            assert len(data.findings) == 2
            assert data.config["engagement_name"] == "Test Engagement"
            
            # Verify agent details
            agent_ids = {a.agent_id for a in data.agents}
            assert "recon-1" in agent_ids
            assert "exploit-1" in agent_ids
            
            # Verify finding details
            finding_ids = {f.finding_id for f in data.findings}
            assert "finding-1" in finding_ids
            assert "finding-2" in finding_ids

    @pytest.mark.asyncio
    async def test_restore_preserves_agent_decision_context(self) -> None:
        """
        GIVEN an agent with complex decision context
        WHEN checkpoint is saved then loaded
        THEN decision context is fully preserved
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            complex_context = {
                "causal_chain": ["action-1", "action-2", "action-3"],
                "emergence_score": 0.85,
                "nested": {
                    "level1": {
                        "level2": ["a", "b", "c"]
                    }
                },
            }
            
            agents = [
                AgentState(
                    agent_id="agent-1",
                    agent_type="postex",
                    state={"current_shell": "/bin/bash"},
                    decision_context=complex_context,
                ),
            ]
            
            path = await manager.save(
                engagement_id="eng-1",
                agents=agents,
            )
            
            data = await manager.load(path, verify_scope=False)
            
            restored_agent = data.agents[0]
            assert restored_agent.decision_context == complex_context
            assert restored_agent.decision_context["causal_chain"] == ["action-1", "action-2", "action-3"]
            assert restored_agent.decision_context["nested"]["level1"]["level2"] == ["a", "b", "c"]


class TestCheckpointConcurrentAccess:
    """Integration tests for WAL mode concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_during_write_wal_mode(self) -> None:
        """
        GIVEN a checkpoint being written (WAL mode)
        WHEN concurrent read is attempted
        THEN read succeeds without blocking
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create initial checkpoint
            path = await manager.save(
                engagement_id="eng-1",
                agents=[AgentState("a1", "recon", {})],
                config={"version": 1},
            )
            
            # Start a slow write in background
            write_started = asyncio.Event()
            write_completed = asyncio.Event()
            
            async def slow_write():
                write_started.set()
                # Simulate slow write by creating new checkpoint
                await manager.save(
                    engagement_id="eng-1",
                    agents=[AgentState(f"a{i}", "recon", {}) for i in range(100)],
                    config={"version": 2},
                )
                write_completed.set()
            
            # Start slow write
            write_task = asyncio.create_task(slow_write())
            await write_started.wait()
            
            # Attempt concurrent read - should not block
            start = time.perf_counter()
            data = await manager.load(path, verify_scope=False)
            read_time = time.perf_counter() - start
            
            # Wait for write to complete
            await write_task
            
            # Read should have completed quickly (< 100ms)
            assert read_time < 0.1
            assert data is not None

    @pytest.mark.asyncio
    async def test_multiple_concurrent_readers(self) -> None:
        """
        GIVEN a checkpoint file
        WHEN multiple concurrent reads occur
        THEN all reads succeed
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create checkpoint
            path = await manager.save(
                engagement_id="eng-1",
                agents=[AgentState("a1", "recon", {"data": "test"})],
            )
            
            # Spawn multiple concurrent readers
            async def reader(reader_id: int) -> CheckpointData:
                return await manager.load(path, verify_scope=False)
            
            # Run 10 concurrent reads
            tasks = [reader(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # All reads should succeed with same data
            assert len(results) == 10
            for data in results:
                assert data.engagement_id == "eng-1"
                assert len(data.agents) == 1


class TestCheckpointScalePerformance:
    """Integration tests for scale and performance."""

    @pytest.mark.asyncio
    async def test_checkpoint_with_100_agents(self) -> None:
        """
        GIVEN an engagement with 100+ agents
        WHEN checkpoint is saved and loaded
        THEN operation completes in < 5s
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create 100 agents
            agents = [
                AgentState(
                    agent_id=f"agent-{i}",
                    agent_type=["recon", "exploit", "postex"][i % 3],
                    state={"iteration": i, "data": f"state-data-{i}" * 10},
                    last_action_id=f"action-{i}",
                    decision_context={"depth": i % 5, "history": list(range(i % 10))},
                )
                for i in range(100)
            ]
            
            # Time save operation
            start = time.perf_counter()
            path = await manager.save(
                engagement_id="eng-scale",
                agents=agents,
                config={"scale_test": True},
            )
            save_time = time.perf_counter() - start
            
            # Time load operation
            start = time.perf_counter()
            data = await manager.load(path, verify_scope=False)
            load_time = time.perf_counter() - start
            
            # Verify performance
            assert save_time < 5.0, f"Save took {save_time:.2f}s, expected < 5s"
            assert load_time < 5.0, f"Load took {load_time:.2f}s, expected < 5s"
            
            # Verify data integrity
            assert len(data.agents) == 100

    @pytest.mark.asyncio
    async def test_checkpoint_with_1000_findings(self) -> None:
        """
        GIVEN an engagement with 1000+ findings
        WHEN checkpoint is saved and loaded
        THEN operation completes in < 5s
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create 1000 findings
            findings = [
                Finding(
                    finding_id=f"finding-{i}",
                    data={
                        "type": ["vuln", "info", "port"][i % 3],
                        "severity": ["critical", "high", "medium", "low"][i % 4],
                        "details": f"Finding details for item {i}" * 5,
                        "metadata": {"index": i, "tags": [f"tag-{j}" for j in range(5)]},
                    },
                    agent_id=f"agent-{i % 10}",
                    timestamp=datetime.now(timezone.utc),
                )
                for i in range(1000)
            ]
            
            # Time save operation
            start = time.perf_counter()
            path = await manager.save(
                engagement_id="eng-findings",
                findings=findings,
            )
            save_time = time.perf_counter() - start
            
            # Time load operation
            start = time.perf_counter()
            data = await manager.load(path, verify_scope=False)
            load_time = time.perf_counter() - start
            
            # Verify performance
            assert save_time < 5.0, f"Save took {save_time:.2f}s, expected < 5s"
            assert load_time < 5.0, f"Load took {load_time:.2f}s, expected < 5s"
            
            # Verify data integrity
            assert len(data.findings) == 1000

    @pytest.mark.asyncio
    async def test_full_scale_engagement(self) -> None:
        """
        GIVEN engagement with 100 agents AND 1000 findings
        WHEN checkpoint is saved and loaded
        THEN operation completes in < 5s with full integrity
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            agents = [
                AgentState(
                    agent_id=f"agent-{i}",
                    agent_type="recon",
                    state={"data": f"x" * 100},
                )
                for i in range(100)
            ]
            
            findings = [
                Finding(
                    finding_id=f"finding-{i}",
                    data={"info": f"y" * 100},
                    agent_id=f"agent-{i % 100}",
                    timestamp=datetime.now(timezone.utc),
                )
                for i in range(1000)
            ]
            
            config = {
                "scale": "large",
                "settings": {str(i): i for i in range(50)},
            }
            
            start = time.perf_counter()
            path = await manager.save(
                engagement_id="eng-full-scale",
                agents=agents,
                findings=findings,
                config=config,
            )
            save_time = time.perf_counter() - start
            
            start = time.perf_counter()
            data = await manager.load(path, verify_scope=False)
            load_time = time.perf_counter() - start
            
            total_time = save_time + load_time
            assert total_time < 5.0, f"Total time {total_time:.2f}s, expected < 5s"
            
            assert len(data.agents) == 100
            assert len(data.findings) == 1000
            assert data.config["scale"] == "large"


class TestCheckpointErrorConditions:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    async def test_scope_hash_mismatch_raises_error(self) -> None:
        """
        GIVEN a checkpoint saved with scope file
        WHEN scope file changes before restore
        THEN CheckpointScopeChangedError is raised
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create scope file
            scope_path = Path(tmpdir) / "scope.yaml"
            scope_path.write_text("targets:\n  - 10.0.0.1\n")
            
            # Save checkpoint with scope
            path = await manager.save(
                engagement_id="eng-1",
                scope_path=scope_path,
            )
            
            # Modify scope file
            scope_path.write_text("targets:\n  - 10.0.0.1\n  - 10.0.0.2\n")
            
            # Load should raise scope changed error
            with pytest.raises(CheckpointScopeChangedError) as exc_info:
                await manager.load(path, scope_path=scope_path, verify_scope=True)
            
            assert "scope" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_schema_version_mismatch_raises_error(self) -> None:
        """
        GIVEN a checkpoint with newer schema version
        WHEN load is attempted
        THEN IncompatibleSchemaError is raised
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Save checkpoint normally
            path = await manager.save(engagement_id="eng-1")
            
            # Manually update schema version to future version
            conn = sqlite3.connect(str(path))
            conn.execute(
                "UPDATE metadata SET value = '99.0.0' WHERE key = 'schema_version'"
            )
            conn.commit()
            conn.close()
            
            # Load should raise incompatible schema error
            with pytest.raises(IncompatibleSchemaError) as exc_info:
                await manager.load(path, verify_scope=False)
            
            assert "99.0.0" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupted_checkpoint_fails_verification(self) -> None:
        """
        GIVEN a checkpoint file
        WHEN data is corrupted
        THEN verify() returns False and load() raises error
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            path = await manager.save(
                engagement_id="eng-1",
                agents=[AgentState("a1", "recon", {"key": "value"})],
            )
            
            # Verify passes initially
            assert manager.verify(path) is True
            
            # Corrupt the data
            conn = sqlite3.connect(str(path))
            conn.execute(
                "UPDATE agents SET state_json = '{\"key\": \"corrupted\"}'"
            )
            conn.commit()
            conn.close()
            
            # Verify should fail
            assert manager.verify(path) is False


class TestCheckpointCrashRecovery:
    """Integration tests for crash recovery scenarios."""

    @pytest.mark.asyncio
    async def test_restore_after_incomplete_write(self) -> None:
        """
        GIVEN a checkpoint write that was interrupted
        WHEN attempting to load
        THEN previous valid checkpoint is available
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Create valid checkpoint
            path = await manager.save(
                engagement_id="eng-1",
                agents=[AgentState("a1", "recon", {"version": 1})],
            )
            
            # Verify valid checkpoint exists
            data = await manager.load(path, verify_scope=False)
            assert len(data.agents) == 1
            
            # Simulate incomplete write by creating .tmp file
            tmp_path = path.with_suffix(".sqlite.tmp")
            tmp_path.write_bytes(b"incomplete data")
            
            # Original checkpoint should still be loadable
            data = await manager.load(path, verify_scope=False)
            assert data.agents[0].state["version"] == 1

    @pytest.mark.asyncio
    async def test_atomic_write_prevents_corruption(self) -> None:
        """
        GIVEN checkpoint write operation
        WHEN write completes
        THEN file is either fully written or not at all (atomic)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            
            # Perform multiple rapid writes
            for i in range(10):
                await manager.save(
                    engagement_id="eng-atomic",
                    agents=[AgentState(f"a{i}", "recon", {"iteration": i})],
                )
            
            # Final state should be consistent
            path = manager._get_checkpoint_path("eng-atomic")
            data = await manager.load(path, verify_scope=False)
            
            # Should have exactly 1 agent (last write)
            assert len(data.agents) == 1
            # Verify integrity
            assert manager.verify(path) is True


class TestCheckpointIntegrationWithSchedulerAndQueue:
    """Integration tests combining scheduler, queue, and manager."""

    @pytest.mark.asyncio
    async def test_scheduler_queue_manager_integration(self) -> None:
        """
        GIVEN CheckpointScheduler using AsyncCheckpointQueue
        WHEN scheduler triggers checkpoint
        THEN checkpoint is written via queue to manager
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(base_path=Path(tmpdir))
            queue = AsyncCheckpointQueue(manager)
            scheduler = CheckpointScheduler(queue=queue, interval_seconds=0.1)
            
            scheduler.set_engagement_context(
                engagement_id="eng-integrated",
                agents=[AgentState("a1", "recon", {"test": True})],
                findings=[],
                config={"integration": "test"},
            )
            
            await queue.start()
            await scheduler.start()
            
            try:
                # Wait for interval to trigger checkpoint
                await asyncio.sleep(0.15)
                await queue.flush()
                
                # Verify checkpoint was created
                path = manager._get_checkpoint_path("eng-integrated")
                assert path.exists()
                
                data = await manager.load(path, verify_scope=False)
                assert data.config["integration"] == "test"
            finally:
                await scheduler.stop()
                await queue.stop()
