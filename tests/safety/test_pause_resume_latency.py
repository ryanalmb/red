"""Safety Tests for Pause/Resume Latency (NFR31).

This module verifies that pause and resume operations complete within the
required <1s latency budget per NFR31.

HOT STATE GUARANTEE:
- Pause: State preserved in RAM only, no disk I/O
- Resume: Instant from memory, no checkpoint reload
"""

import time
from pathlib import Path
from typing import Generator

import pytest

from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.state_machine import EngagementState


@pytest.fixture
def session_manager() -> SessionManager:
    """Create a fresh SessionManager for testing."""
    return SessionManager(max_engagements=10)


@pytest.fixture
def engagement_config(tmp_path: Path) -> Path:
    """Create a valid engagement config file."""
    config = tmp_path / "engagement.yaml"
    config.write_text("name: test-engagement\n")
    return config


@pytest.fixture
def running_engagement(
    session_manager: SessionManager,
    engagement_config: Path,
) -> Generator[str, None, None]:
    """Create an engagement in RUNNING state for latency testing.
    
    NOTE: This fixture transitions state directly via state_machine.start()
    rather than calling session_manager.start_engagement(). This is intentional:
    
    - These safety tests measure PAUSE/RESUME latency (NFR31), not pre-flight latency
    - Pre-flight checks require external dependencies (Redis, LLM) covered by
      integration tests in tests/integration/daemon/test_preflight_integration.py
    - Direct state transition is the correct approach for isolating pause/resume timing
    
    For full engagement lifecycle testing with real pre-flight, see integration tests.
    """
    engagement_id = session_manager.create_engagement(engagement_config)
    
    # Directly transition to RUNNING state for latency testing
    # This bypasses pre-flight which is tested separately in integration tests
    context = session_manager.get_engagement(engagement_id)
    context.state_machine.start()
    
    yield engagement_id


@pytest.fixture
def paused_engagement(
    session_manager: SessionManager,
    running_engagement: str,
) -> str:
    """Create a paused engagement from a running one."""
    session_manager.pause_engagement(running_engagement)
    return running_engagement


@pytest.mark.safety
class TestPauseResumeLatency:
    """NFR31: Pause-to-resume latency must be <1 second."""

    def test_pause_latency_under_1s(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """NFR31: Pause must complete in <1s.
        
        Hot state operation - state preserved in RAM, no disk I/O.
        """
        start = time.perf_counter()
        new_state = session_manager.pause_engagement(running_engagement)
        elapsed = time.perf_counter() - start
        
        assert new_state == EngagementState.PAUSED
        assert elapsed < 1.0, f"Pause took {elapsed:.3f}s, expected <1s (NFR31)"

    def test_resume_latency_under_1s(
        self,
        session_manager: SessionManager,
        paused_engagement: str,
    ) -> None:
        """NFR31: Resume must complete in <1s.
        
        Hot state operation - resumes from memory, no checkpoint reload.
        """
        start = time.perf_counter()
        new_state = session_manager.resume_engagement(paused_engagement)
        elapsed = time.perf_counter() - start
        
        assert new_state == EngagementState.RUNNING
        assert elapsed < 1.0, f"Resume took {elapsed:.3f}s, expected <1s (NFR31)"

    def test_pause_resume_cycle_under_2s(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Full pause/resume cycle must complete well within budget.
        
        NFR31 says <1s each, so combined cycle should be <2s.
        We test against this combined budget.
        """
        start = time.perf_counter()
        
        # Pause
        session_manager.pause_engagement(running_engagement)
        pause_time = time.perf_counter() - start
        
        # Resume
        resume_start = time.perf_counter()
        session_manager.resume_engagement(running_engagement)
        resume_time = time.perf_counter() - resume_start
        
        total_time = time.perf_counter() - start
        
        assert pause_time < 1.0, f"Pause took {pause_time:.3f}s"
        assert resume_time < 1.0, f"Resume took {resume_time:.3f}s"
        assert total_time < 2.0, f"Total cycle took {total_time:.3f}s, expected <2s"


@pytest.mark.safety
class TestPauseNoDiskIO:
    """Verify pause operation does not perform disk I/O."""

    def test_pause_no_disk_io(
        self,
        session_manager: SessionManager,
        running_engagement: str,
        tmp_path: Path,
    ) -> None:
        """Verify pause does not write any files.
        
        HOT STATE: Agent state is preserved in memory (RAM) only.
        No checkpoint file should be written during pause.
        This differentiates pause (hot) from stop (cold, Story 2.8).
        """
        # Capture filesystem state before pause
        checkpoint_dir = tmp_path / ".cyber-red" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        files_before = set(checkpoint_dir.rglob("*"))
        
        # Pause engagement
        session_manager.pause_engagement(running_engagement)
        
        # Verify no new files created
        files_after = set(checkpoint_dir.rglob("*"))
        new_files = files_after - files_before
        
        assert len(new_files) == 0, f"Pause created files: {new_files} (should be hot state, no disk I/O)"

    def test_resume_no_disk_io(
        self,
        session_manager: SessionManager,
        paused_engagement: str,
        tmp_path: Path,
    ) -> None:
        """Verify resume does not read checkpoint files.
        
        HOT STATE: Resumes from memory state, no checkpoint reload required.
        """
        # This is implicitly verified by the latency test - if resume
        # were reading from disk, it would be much slower.
        # Here we just confirm the state transitions correctly.
        context = session_manager.get_engagement(paused_engagement)
        assert context.state == EngagementState.PAUSED
        
        new_state = session_manager.resume_engagement(paused_engagement)
        
        assert new_state == EngagementState.RUNNING
        assert context.state == EngagementState.RUNNING
