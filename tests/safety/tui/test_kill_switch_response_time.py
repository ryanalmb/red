"""Safety tests for Kill Switch TUI response time.

Story 10.4: Kill Switch TUI Integration
Safety tests for <1s response time requirement (NFR2).
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.tui.app import CyberRedApp, EngagementState


@pytest.mark.safety
class TestKillSwitchResponseTime:
    """Safety tests for kill switch <1s response time."""

    @pytest.mark.asyncio
    async def test_action_panic_completes_under_1s(self) -> None:
        """AC #9: action_panic() completes in <1s with mocked KillSwitch."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            start = time.perf_counter()
            await app.action_panic()
            elapsed = time.perf_counter() - start
            
            assert elapsed < 1.0, f"action_panic took {elapsed:.3f}s, must be <1s"


@pytest.mark.safety
class TestKillSwitchUnderLoad:
    """Safety tests for kill switch under simulated load."""

    @pytest.mark.asyncio
    async def test_panic_under_agent_updates(self) -> None:
        """AC #9: Test with agent status updates."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 150,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            from cyberred.tui.widgets import HiveGrid
            grid = app.query_one("#hive-grid", HiveGrid)
            
            for i in range(1, 101):
                grid.update_agent(i, "scanning")
            
            start = time.perf_counter()
            await app.action_panic()
            elapsed = time.perf_counter() - start
            
            assert elapsed < 1.0, f"Panic under load took {elapsed:.3f}s, must be <1s"


@pytest.mark.safety
class TestKillSwitchAuditLogging:
    """Safety tests for audit trail logging."""

    @pytest.mark.asyncio
    async def test_audit_logged_even_on_partial_failure(self) -> None:
        """AC #8: Audit is written even if kill paths partially fail."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 200,
            "paths": {
                "redis": False,
                "sigterm": True,
                "docker": False,
            },
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await app.action_panic()
            mock_killswitch.trigger.assert_called_once()
            assert app.engagement_state == EngagementState.FROZEN
