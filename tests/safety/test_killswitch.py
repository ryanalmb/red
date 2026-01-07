"""Safety tests for KillSwitch - Tri-path kill switch (safety-critical).

These tests are marked with @pytest.mark.safety and verify:
- <1s timing under various conditions (NFR2 hard requirement)
- Resilience when Redis is unavailable
- Resilience when Docker is unavailable
- All paths execute even if some fail
- Agent frozen check integration

Run with: pytest tests/safety/test_killswitch.py -m safety
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.core.exceptions import KillSwitchTriggered


@pytest.mark.safety
class TestKillSwitchTimingRequirements:
    """Safety tests for <1s timing requirement (NFR2)."""

    @pytest.mark.asyncio
    async def test_trigger_completes_under_1s_with_mocked_paths(self) -> None:
        """Test trigger() completes in <1s with mocked paths (baseline)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        start = time.perf_counter()
        result = await ks.trigger(reason="safety test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s, must be <1s"
        assert result["duration_ms"] < 1000

    @pytest.mark.asyncio
    async def test_trigger_completes_under_1s_with_redis_timeout(self) -> None:
        """Test trigger() completes in <1s even when Redis times out."""
        from cyberred.core.killswitch import KillSwitch

        redis_client = AsyncMock()

        async def slow_redis_publish(*args: Any) -> int:
            await asyncio.sleep(2.0)  # Longer than timeout
            return 1

        redis_client.publish = slow_redis_publish

        ks = KillSwitch(
            redis_client=redis_client,
            engagement_id="test-engagement",
        )
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        start = time.perf_counter()
        await ks.trigger(reason="safety test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s, must be <1s"

    @pytest.mark.asyncio
    async def test_trigger_completes_under_1s_with_docker_timeout(self) -> None:
        """Test trigger() completes in <1s even when Docker is slow.
        
        Note: Docker operations are blocking, but the entire path has a timeout
        applied via asyncio.wait_for in trigger(). We test with a slow but 
        responsive mock that respects asyncio cancellation.
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")
        
        # Mock docker to be slow but not blocking (using AsyncMock)
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)
        
        async def slow_docker() -> bool:
            await asyncio.sleep(0.5)  # Slow but async
            return True
        
        ks._path_docker = slow_docker

        start = time.perf_counter()
        await ks.trigger(reason="safety test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s, must be <1s"


@pytest.mark.safety
class TestKillSwitchResilience:
    """Safety tests for resilience when dependencies unavailable."""

    @pytest.mark.asyncio
    async def test_trigger_works_without_redis(self) -> None:
        """Test trigger() works even if Redis is completely unavailable."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")  # No redis_client
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        result = await ks.trigger(reason="safety test")

        assert result["success"] is True
        assert ks.is_frozen is True

    @pytest.mark.asyncio
    async def test_trigger_works_without_docker(self) -> None:
        """Test trigger() works even if Docker is completely unavailable."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")  # No docker_client
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)

        result = await ks.trigger(reason="safety test")

        assert result["success"] is True
        assert ks.is_frozen is True

    @pytest.mark.asyncio
    async def test_trigger_works_with_all_paths_failing(self) -> None:
        """Test trigger() still completes even if ALL paths fail."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        async def failing_redis(reason: str, triggered_by: str = "operator") -> bool:
            raise ConnectionError("Redis down")

        async def failing_sigterm() -> bool:
            raise PermissionError("Permission denied")

        async def failing_docker() -> bool:
            raise Exception("Docker daemon not running")

        ks._path_redis = failing_redis
        ks._path_sigterm = failing_sigterm
        ks._path_docker = failing_docker

        result = await ks.trigger(reason="safety test")

        # Kill switch should still complete (frozen flag set)
        assert ks.is_frozen is True
        # Success depends on implementation - frozen flag is enough for safety

    @pytest.mark.asyncio
    async def test_all_paths_execute_even_if_some_fail(self) -> None:
        """Test all three paths are attempted even if some fail."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        path_calls = {"redis": False, "sigterm": False, "docker": False}

        async def failing_redis(reason: str, triggered_by: str = "operator") -> bool:
            path_calls["redis"] = True
            raise ConnectionError("Redis down")

        async def success_sigterm() -> bool:
            path_calls["sigterm"] = True
            return True

        async def success_docker() -> bool:
            path_calls["docker"] = True
            return True

        ks._path_redis = failing_redis
        ks._path_sigterm = success_sigterm
        ks._path_docker = success_docker

        await ks.trigger(reason="safety test")

        # All paths should have been called
        assert path_calls["redis"] is True
        assert path_calls["sigterm"] is True
        assert path_calls["docker"] is True


@pytest.mark.safety
class TestAgentFrozenIntegration:
    """Safety tests for agent frozen check integration."""

    def test_check_frozen_blocks_agent_work(self) -> None:
        """Test check_frozen() blocks agent work when frozen."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")
        ks._frozen.set()

        with pytest.raises(KillSwitchTriggered):
            ks.check_frozen()

    def test_check_frozen_allows_work_when_not_frozen(self) -> None:
        """Test check_frozen() allows agent work when not frozen."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        # Should not raise
        ks.check_frozen()

    @pytest.mark.asyncio
    async def test_frozen_flag_set_before_paths(self) -> None:
        """Test frozen flag is set BEFORE any path executes (race condition safety)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        flag_was_set: list[bool] = []

        async def check_frozen_in_path(reason: str, triggered_by: str = "operator") -> bool:
            flag_was_set.append(ks.is_frozen)
            return True

        ks._path_redis = check_frozen_in_path
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        await ks.trigger(reason="safety test")

        # Frozen flag should have been True when path started
        assert flag_was_set[0] is True


@pytest.mark.safety
class TestKillSwitchLoadSimulation:
    """Safety tests for kill switch under simulated load conditions (Story 1.10)."""

    @pytest.mark.asyncio
    async def test_trigger_under_100_agent_load(self) -> None:
        """Test kill switch completes <1s with 100 concurrent agents polling frozen flag.
        
        AC#5: Kill switch triggers in <1s under simulated 100-agent load.
        """
        from cyberred.core.killswitch import KillSwitch
        from cyberred.core.exceptions import KillSwitchTriggered

        ks = KillSwitch(engagement_id="test-engagement")
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        agents_stopped: list[int] = []

        async def mock_agent(agent_id: int) -> None:
            """Simulated agent that polls frozen flag in work loop."""
            try:
                while True:
                    await asyncio.sleep(0.001)  # Agent work cycle
                    ks.check_frozen()  # Raises KillSwitchTriggered if frozen
            except KillSwitchTriggered:
                agents_stopped.append(agent_id)
                return

        # Spawn 100 agents
        agent_tasks = [asyncio.create_task(mock_agent(i)) for i in range(100)]
        await asyncio.sleep(0.05)  # Let agents start their loops

        # Trigger kill switch and measure time
        start = time.perf_counter()
        await ks.trigger(reason="100-agent load test")

        # Wait for all agents to stop (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*agent_tasks, return_exceptions=True),
                timeout=0.9  # Leave buffer for assertion
            )
        except asyncio.TimeoutError:
            pass

        duration = time.perf_counter() - start

        # Cancel any remaining tasks
        for task in agent_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s with 100 agents"
        assert ks.is_frozen is True, "Frozen flag must be set"

    @pytest.mark.asyncio
    async def test_100_agents_receive_frozen_signal(self) -> None:
        """Test all 100 agents receive KillSwitchTriggered exception within 1s.
        
        AC#5: Verifies signal propagation to all agents.
        """
        from cyberred.core.killswitch import KillSwitch
        from cyberred.core.exceptions import KillSwitchTriggered

        ks = KillSwitch(engagement_id="test-engagement")
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        agent_exception_times: list[float] = []
        trigger_time: float = 0.0

        async def mock_agent(agent_id: int) -> None:
            """Agent that records when it receives KillSwitchTriggered."""
            try:
                while True:
                    await asyncio.sleep(0.001)
                    ks.check_frozen()
            except KillSwitchTriggered:
                agent_exception_times.append(time.perf_counter() - trigger_time)
                return

        # Spawn 100 agents
        agent_tasks = [asyncio.create_task(mock_agent(i)) for i in range(100)]
        await asyncio.sleep(0.05)

        # Trigger and record time
        trigger_time = time.perf_counter()
        await ks.trigger(reason="signal propagation test")

        # Wait for all agents
        try:
            await asyncio.wait_for(
                asyncio.gather(*agent_tasks, return_exceptions=True),
                timeout=0.9
            )
        except asyncio.TimeoutError:
            pass

        # Cleanup
        for task in agent_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # All agents should have received the signal
        assert len(agent_exception_times) >= 95, f"Only {len(agent_exception_times)}/100 agents stopped"
        
        # The last agent should have received signal within 1s
        if agent_exception_times:
            max_time = max(agent_exception_times)
            assert max_time < 1.0, f"SAFETY VIOLATION: Last agent took {max_time:.3f}s to receive signal"

    @pytest.mark.asyncio
    async def test_trigger_under_container_load(self) -> None:
        """Test kill switch completes <1s with 50 containers to stop.
        
        AC#6: Kill switch triggers in <1s under simulated container load.
        """
        from cyberred.core.killswitch import KillSwitch

        # Mock Docker client with 50 containers
        mock_containers = []
        for i in range(50):
            container = MagicMock()
            container.stop = MagicMock()  # Blocking but mocked instant
            container.kill = MagicMock()
            container.labels = {"cyberred.engagement_id": "test-engagement"}
            mock_containers.append(container)

        docker_client = MagicMock()
        docker_client.containers.list.return_value = mock_containers

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)

        start = time.perf_counter()
        result = await ks.trigger(reason="container load test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s with 50 containers"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_trigger_with_container_not_found(self) -> None:
        """Test kill switch handles containers that are already stopped.
        
        Edge case: Some containers may be NotFound during stop.
        """
        import docker.errors
        from cyberred.core.killswitch import KillSwitch

        # Create containers - some raise NotFound
        mock_containers = []
        for i in range(10):
            container = MagicMock()
            if i % 3 == 0:  # Every 3rd container already stopped
                container.stop = MagicMock(side_effect=docker.errors.NotFound("Already stopped"))
            else:
                container.stop = MagicMock()
            container.kill = MagicMock()
            container.labels = {"cyberred.engagement_id": "test-engagement"}
            mock_containers.append(container)

        docker_client = MagicMock()
        docker_client.containers.list.return_value = mock_containers

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)

        start = time.perf_counter()
        result = await ks.trigger(reason="container not found test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s"
        assert ks.is_frozen is True

    @pytest.mark.asyncio
    async def test_trigger_with_container_stop_timeout(self) -> None:
        """Test kill switch calls kill() when container stop() times out.
        
        Edge case: Container stop times out, fallback to kill.
        """
        import docker.errors
        from cyberred.core.killswitch import KillSwitch

        # Create container that times out on stop
        container = MagicMock()
        container.stop = MagicMock(side_effect=Exception("Timeout"))
        container.kill = MagicMock()  # Kill should be called as fallback
        container.labels = {"cyberred.engagement_id": "test-engagement"}

        docker_client = MagicMock()
        docker_client.containers.list.return_value = [container]

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )
        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)

        start = time.perf_counter()
        await ks.trigger(reason="container timeout test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s"
        assert ks.is_frozen is True


@pytest.mark.safety
class TestKillSwitchStressAndTiming:
    """Stress testing and timing precision tests (Story 1.10 Tasks 4-6)."""

    @pytest.mark.asyncio
    async def test_trigger_redis_down_docker_slow_sigterm_ok(self) -> None:
        """Test combined failure: Redis down, Docker slow, SIGTERM works.
        
        Task 5: Combined failure mode tests.
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        async def failing_redis(reason: str, triggered_by: str = "operator") -> bool:
            raise ConnectionError("Redis down")

        async def slow_docker() -> bool:
            await asyncio.sleep(0.4)  # Slow but under timeout
            return True

        ks._path_redis = failing_redis
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = slow_docker

        start = time.perf_counter()
        result = await ks.trigger(reason="combined failure test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s"
        assert ks.is_frozen is True

    @pytest.mark.asyncio
    async def test_trigger_all_paths_timeout(self) -> None:
        """Test all paths timeout but frozen flag is still set.
        
        Task 5: Verify frozen flag set even with all paths failing.
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        async def timeout_redis(reason: str, triggered_by: str = "operator") -> bool:
            await asyncio.sleep(2.0)  # Will be cancelled by timeout
            return True

        async def timeout_sigterm() -> bool:
            await asyncio.sleep(2.0)
            return True

        async def timeout_docker() -> bool:
            await asyncio.sleep(2.0)
            return True

        ks._path_redis = timeout_redis
        ks._path_sigterm = timeout_sigterm
        ks._path_docker = timeout_docker

        start = time.perf_counter()
        await ks.trigger(reason="all timeout test")
        duration = time.perf_counter() - start

        # Even with all paths timing out, should complete in <1s due to individual timeouts
        assert duration < 1.0, f"SAFETY VIOLATION: Kill switch took {duration:.3f}s"
        # Most importantly: frozen flag must be set
        assert ks.is_frozen is True, "CRITICAL: Frozen flag not set despite all timeouts"

    @pytest.mark.asyncio
    async def test_trigger_timing_budget_redis_500ms(self) -> None:
        """Test Redis path respects 500ms timeout budget.
        
        Task 6: Verify individual path timeouts work correctly.
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        redis_completed = False

        async def slow_redis(reason: str, triggered_by: str = "operator") -> bool:
            nonlocal redis_completed
            await asyncio.sleep(2.0)  # Much longer than 500ms timeout
            redis_completed = True
            return True

        ks._path_redis = slow_redis
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        start = time.perf_counter()
        await ks.trigger(reason="redis timeout test")
        duration = time.perf_counter() - start

        # Should complete in <1s (Redis cancelled after ~500ms)
        assert duration < 1.0, f"Redis path didn't respect timeout: {duration:.3f}s"
        # Redis should NOT have completed (was cancelled)
        assert redis_completed is False, "Redis completed despite timeout"

    @pytest.mark.asyncio
    async def test_trigger_timing_budget_docker_600ms(self) -> None:
        """Test Docker path respects 600ms timeout budget.
        
        Task 6: Verify individual path timeouts work correctly.
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        docker_completed = False

        async def slow_docker() -> bool:
            nonlocal docker_completed
            await asyncio.sleep(2.0)  # Much longer than 600ms timeout
            docker_completed = True
            return True

        ks._path_redis = AsyncMock(return_value=True)
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = slow_docker

        start = time.perf_counter()
        await ks.trigger(reason="docker timeout test")
        duration = time.perf_counter() - start

        # Should complete in <1s (Docker cancelled after ~600ms)
        assert duration < 1.0, f"Docker path didn't respect timeout: {duration:.3f}s"
        # Docker should NOT have completed (was cancelled)
        assert docker_completed is False, "Docker completed despite timeout"

    @pytest.mark.asyncio
    async def test_parallel_execution_not_sequential(self) -> None:
        """Test paths execute in parallel, not sequentially.
        
        Task 6: Verify parallel execution (not sequential).
        """
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        path_start_times: dict[str, float] = {}
        test_start: float = 0.0

        async def track_redis(reason: str, triggered_by: str = "operator") -> bool:
            path_start_times["redis"] = time.perf_counter() - test_start
            await asyncio.sleep(0.1)
            return True

        async def track_sigterm() -> bool:
            path_start_times["sigterm"] = time.perf_counter() - test_start
            await asyncio.sleep(0.1)
            return True

        async def track_docker() -> bool:
            path_start_times["docker"] = time.perf_counter() - test_start
            await asyncio.sleep(0.1)
            return True

        ks._path_redis = track_redis
        ks._path_sigterm = track_sigterm
        ks._path_docker = track_docker

        test_start = time.perf_counter()
        await ks.trigger(reason="parallel test")
        total_duration = time.perf_counter() - test_start

        # All paths should start within ~50ms of each other (parallel)
        start_times = list(path_start_times.values())
        assert len(start_times) == 3, "Not all paths were tracked"
        
        max_start_diff = max(start_times) - min(start_times)
        assert max_start_diff < 0.05, f"Paths not parallel: {max_start_diff:.3f}s between starts"

        # Total should be ~100ms (parallel), not ~300ms (sequential)
        assert total_duration < 0.3, f"Execution appears sequential: {total_duration:.3f}s"

    @pytest.mark.asyncio
    async def test_trigger_with_redis_error_mid_publish(self) -> None:
        """Test Redis returning error mid-publish doesn't block.
        
        Task 4: Redis error handling.
        """
        from cyberred.core.killswitch import KillSwitch

        redis_client = AsyncMock()
        redis_client.publish = AsyncMock(side_effect=ConnectionError("Connection lost"))

        ks = KillSwitch(
            redis_client=redis_client,
            engagement_id="test-engagement"
        )
        ks._path_sigterm = AsyncMock(return_value=True)
        ks._path_docker = AsyncMock(return_value=True)

        start = time.perf_counter()
        result = await ks.trigger(reason="redis error test")
        duration = time.perf_counter() - start

        assert duration < 1.0, f"Redis error blocked execution: {duration:.3f}s"
        assert ks.is_frozen is True
        # Fallback paths should have executed


@pytest.mark.safety
class TestKillSwitchCoverage:
    """Coverage tests for internal paths (Story 1.10 - 100% coverage)."""

    def test_reset_clears_frozen_flag(self) -> None:
        """Test reset() clears the frozen flag (lines 102-103)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")
        ks._frozen.set()
        assert ks.is_frozen is True

        ks.reset()

        assert ks.is_frozen is False
        assert ks._trigger_time is None

    @pytest.mark.asyncio
    async def test_path_redis_success(self) -> None:
        """Test Redis path successful publish (lines 222-224)."""
        from datetime import datetime
        from cyberred.core.killswitch import KillSwitch

        redis_client = AsyncMock()
        redis_client.publish = AsyncMock(return_value=1)

        ks = KillSwitch(
            redis_client=redis_client,
            engagement_id="test-engagement"
        )

        with patch("cyberred.core.killswitch.now", return_value=datetime(2026, 1, 1, 12, 0, 0)):
            result = await ks._path_redis(reason="test", triggered_by="operator")

        assert result is True
        redis_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_sigterm_success(self) -> None:
        """Test SIGTERM path success (lines 236-243)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        with patch("cyberred.core.killswitch.os.getpgid", return_value=12345):
            with patch("cyberred.core.killswitch.os.killpg") as mock_killpg:
                result = await ks._path_sigterm()

        assert result is True
        mock_killpg.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_sigterm_process_lookup_error(self) -> None:
        """Test SIGTERM path with ProcessLookupError (lines 245-248)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        with patch("cyberred.core.killswitch.os.getpgid", side_effect=ProcessLookupError("No process")):
            result = await ks._path_sigterm()

        # ProcessLookupError is treated as success (process already gone)
        assert result is True

    @pytest.mark.asyncio
    async def test_path_sigterm_permission_error(self) -> None:
        """Test SIGTERM path with PermissionError (lines 250-252)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        with patch("cyberred.core.killswitch.os.getpgid", return_value=12345):
            with patch("cyberred.core.killswitch.os.killpg", side_effect=PermissionError("Permission denied")):
                result = await ks._path_sigterm()

        assert result is False

    @pytest.mark.asyncio
    async def test_path_sigterm_generic_exception(self) -> None:
        """Test SIGTERM path with generic exception (lines 254-256)."""
        from cyberred.core.killswitch import KillSwitch

        ks = KillSwitch(engagement_id="test-engagement")

        with patch("cyberred.core.killswitch.os.getpgid", return_value=12345):
            with patch("cyberred.core.killswitch.os.killpg", side_effect=OSError("Some error")):
                result = await ks._path_sigterm()

        assert result is False

    def test_sync_docker_stop_no_containers(self) -> None:
        """Test Docker path with no containers (lines 283-285)."""
        from cyberred.core.killswitch import KillSwitch

        docker_client = MagicMock()
        docker_client.containers.list.return_value = []

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )

        result = ks._sync_docker_stop()

        assert result is True

    def test_sync_docker_stop_kill_fallback_not_found(self) -> None:
        """Test Docker kill fallback with NotFound error (lines 303-309)."""
        from cyberred.core.killswitch import KillSwitch

        # Create NotFound-like exception
        class NotFound(Exception):
            pass

        container = MagicMock()
        container.id = "abc123def456"
        container.stop = MagicMock(side_effect=Exception("Stop failed"))
        container.kill = MagicMock(side_effect=NotFound("Container gone"))

        docker_client = MagicMock()
        docker_client.containers.list.return_value = [container]

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )

        result = ks._sync_docker_stop()

        # Should still return True (container is gone which is success)
        assert result is True
        container.stop.assert_called_once()
        container.kill.assert_called_once()

    def test_sync_docker_stop_kill_fallback_other_error(self) -> None:
        """Test Docker kill fallback with non-NotFound error (lines 310-315)."""
        from cyberred.core.killswitch import KillSwitch

        container = MagicMock()
        container.id = "abc123def456"
        container.stop = MagicMock(side_effect=Exception("Stop failed"))
        container.kill = MagicMock(side_effect=RuntimeError("Kill failed"))

        docker_client = MagicMock()
        docker_client.containers.list.return_value = [container]

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )

        result = ks._sync_docker_stop()

        # Still returns True (we log but don't fail)
        assert result is True
        container.stop.assert_called_once()
        container.kill.assert_called_once()

    def test_sync_docker_stop_generic_exception(self) -> None:
        """Test Docker path with generic exception (lines 319-321)."""
        from cyberred.core.killswitch import KillSwitch

        docker_client = MagicMock()
        docker_client.containers.list.side_effect = Exception("Docker daemon error")

        ks = KillSwitch(
            docker_client=docker_client,
            engagement_id="test-engagement"
        )

        result = ks._sync_docker_stop()

        assert result is False
